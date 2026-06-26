from flask import Blueprint, render_template, request, session, redirect, url_for, flash, g, jsonify, current_app
from database.connection import db
from models.exam import Exam, Question, Option, Subject
from models.attempt import StudentExam, StudentResponse, Result
from routes.auth import login_required
from routes import log_action
from datetime import datetime, timedelta
import random

exam_bp = Blueprint('exam', __name__)

@exam_bp.route('/start/<int:exam_id>', methods=['POST'])
@login_required
def start_exam(exam_id):
    if session.get('role') != 'student':
        return redirect(url_for('admin.dashboard'))
        
    student = g.user.student_profile
    exam = db.session.get(Exam, exam_id)
    
    if not exam:
        flash('Exam not found.', 'danger')
        return redirect(url_for('student.available_exams'))
        
    # Check scheduling window
    now = datetime.utcnow()
    if exam.start_time > now or exam.end_time < now:
        flash('This exam is not active at the current time.', 'danger')
        return redirect(url_for('student.available_exams'))
        
    # Check if student has an in-progress attempt for this exam
    in_progress_attempt = StudentExam.query.filter_by(
        student_id=student.id,
        exam_id=exam_id,
        status='in_progress'
    ).first()
    if in_progress_attempt:
        # Resume existing in-progress attempt
        return redirect(url_for('exam.take_exam', attempt_id=in_progress_attempt.id))
            
    # Create new attempt
    new_attempt = StudentExam(
        student_id=student.id,
        exam_id=exam_id,
        started_at=now,
        status='in_progress'
    )
    db.session.add(new_attempt)
    db.session.commit()
    
    log_action("Exam Started", f"Started attempt for exam: {exam.title}", user_id=g.user.id)
    
    return redirect(url_for('exam.take_exam', attempt_id=new_attempt.id))


@exam_bp.route('/take/<int:attempt_id>')
@login_required
def take_exam(attempt_id):
    attempt = db.session.get(StudentExam, attempt_id)
    
    if not attempt or attempt.student_id != g.user.student_profile.id:
        flash('Invalid exam attempt session.', 'danger')
        return redirect(url_for('student.available_exams'))
        
    if attempt.status == 'submitted':
        return redirect(url_for('exam.view_result', attempt_id=attempt.id))
        
    exam = attempt.exam
    
    # Calculate time left
    now = datetime.utcnow()
    elapsed = now - attempt.started_at
    total_seconds = exam.duration_minutes * 60
    remaining_seconds = max(0, int(total_seconds - elapsed.total_seconds()))
    
    # Auto submit if expired
    if remaining_seconds <= 0:
        return finalize_exam_submission(attempt)
        
    # Random question selection logic - store selected IDs in user session to persist across reloads
    session_key = f'attempt_{attempt.id}_questions'
    if session_key not in session:
        all_questions = Question.query.filter_by(exam_id=exam.id).all()
        q_ids = [q.id for q in all_questions]
        
        if exam.random_questions_count and exam.random_questions_count < len(q_ids):
            q_ids = random.sample(q_ids, exam.random_questions_count)
            
        session[session_key] = q_ids
        
    question_ids = session[session_key]
    
    # Fetch questions in the selected random order (or standard order)
    questions = []
    for q_id in question_ids:
        q = db.session.get(Question, q_id)
        if q:
            questions.append(q)
            
    # Fetch student's currently saved answers for this attempt to populate checkboxes/radios
    saved_responses = StudentResponse.query.filter_by(student_exam_id=attempt.id).all()
    # Map question_id -> list of selected option_ids
    answers = {}
    for r in saved_responses:
        if r.question_id not in answers:
            answers[r.question_id] = []
        answers[r.question_id].append(r.option_id)
        
    return render_template(
        'student/exam_interface.html',
        attempt=attempt,
        exam=exam,
        questions=questions,
        answers=answers,
        remaining_seconds=remaining_seconds
    )


@exam_bp.route('/save_response/<int:attempt_id>', methods=['POST'])
@login_required
def save_response(attempt_id):
    attempt = db.session.get(StudentExam, attempt_id)
    if not attempt or attempt.student_id != g.user.student_profile.id or attempt.status == 'submitted':
        return jsonify({'success': False, 'message': 'Invalid session or already submitted.'}), 403
        
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Missing request payload.'}), 400
        
    question_id = data.get('question_id')
    option_ids = data.get('option_ids', []) # List of selected option IDs
    
    try:
        # Delete previous responses for this question in this attempt
        StudentResponse.query.filter_by(student_exam_id=attempt.id, question_id=question_id).delete()
        
        # Save new responses
        for opt_id in option_ids:
            new_response = StudentResponse(
                student_exam_id=attempt.id,
                question_id=question_id,
                option_id=opt_id
            )
            db.session.add(new_response)
            
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving student response: {e}")
        return jsonify({'success': False, 'message': 'Failed to save responses.'}), 500


@exam_bp.route('/submit/<int:attempt_id>', methods=['POST'])
@login_required
def submit_exam(attempt_id):
    attempt = db.session.get(StudentExam, attempt_id)
    if not attempt or attempt.student_id != g.user.student_profile.id:
        flash('Invalid attempt session.', 'danger')
        return redirect(url_for('student.available_exams'))
        
    if attempt.status == 'submitted':
        return redirect(url_for('exam.view_result', attempt_id=attempt.id))
        
    return finalize_exam_submission(attempt)


def finalize_exam_submission(attempt):
    """Processes grading score calculations, evaluates negative marks, and saves result record."""
    try:
        exam = attempt.exam
        
        # Retrieve selected questions from session or load all of them
        session_key = f'attempt_{attempt.id}_questions'
        question_ids = session.get(session_key)
        if question_ids:
            questions = [db.session.get(Question, q_id) for q_id in question_ids]
            questions = [q for q in questions if q is not None]
        else:
            questions = Question.query.filter_by(exam_id=exam.id).all()
            
        total_exam_marks = sum(q.marks for q in questions)
        obtained_score = 0.0
        
        # Grade each question
        for q in questions:
            correct_opts = {o.id for o in q.options if o.is_correct}
            student_opts = {r.option_id for r in StudentResponse.query.filter_by(student_exam_id=attempt.id, question_id=q.id).all()}
            
            if not student_opts:
                # Question skipped - no marks gained/lost
                continue
                
            if correct_opts == student_opts:
                # Fully correct
                obtained_score += q.marks
            else:
                # Incorrect - apply negative marks
                neg_val = q.negative_marks if q.negative_marks > 0 else exam.negative_marking_val
                obtained_score -= float(neg_val)
                
        # Bound score to 0 as lower limit
        obtained_score = max(0.0, obtained_score)
        
        percentage = (obtained_score / total_exam_marks * 100) if total_exam_marks > 0 else 0.0
        is_passed = percentage >= exam.passing_marks
        
        # Update attempt status
        attempt.submitted_at = datetime.utcnow()
        attempt.status = 'submitted'
        attempt.score = obtained_score
        attempt.is_passed = is_passed
        
        # Create Result record
        # Simple grading system
        grade = 'F'
        if is_passed:
            if percentage >= 90: grade = 'A+'
            elif percentage >= 80: grade = 'A'
            elif percentage >= 70: grade = 'B'
            elif percentage >= 60: grade = 'C'
            else: grade = 'D'
            
        result = Result(
            student_exam_id=attempt.id,
            score=obtained_score,
            percentage=percentage,
            passed=is_passed,
            grade=grade
        )
        db.session.add(result)
        db.session.commit()
        
        # Clear selected questions from session
        session.pop(session_key, None)
        
        log_action("Exam Submitted", f"Submitted exam '{exam.title}' - Scored: {obtained_score}/{total_exam_marks}", user_id=attempt.student.user_id)
        flash('Exam submitted successfully! View your scorecard below.', 'success')
        return redirect(url_for('exam.view_result', attempt_id=attempt.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Grading evaluation failure: {e}")
        flash('An error occurred during submission grading. Please contact administrator.', 'danger')
        return redirect(url_for('student.dashboard'))


@exam_bp.route('/result/<int:attempt_id>')
@login_required
def view_result(attempt_id):
    attempt = db.session.get(StudentExam, attempt_id)
    
    # Security check: User must be student owner or an admin
    if not attempt:
        flash('Result session not found.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    if session.get('role') != 'admin' and attempt.student_id != g.user.student_profile.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    if attempt.status != 'submitted' or not attempt.result:
        flash('This attempt is not submitted or graded yet.', 'warning')
        return redirect(url_for('exam.take_exam', attempt_id=attempt.id))
        
    exam = attempt.exam
    questions = Question.query.filter_by(exam_id=exam.id).all()
    
    # Map questions to correct answers and student choices
    detailed_responses = {}
    for q in questions:
        student_choices = [r.option_id for r in StudentResponse.query.filter_by(student_exam_id=attempt.id, question_id=q.id).all()]
        detailed_responses[q.id] = {
            'student_choices': student_choices,
            'correct_choices': [o.id for o in q.options if o.is_correct]
        }
        
    return render_template(
        'student/result.html',
        attempt=attempt,
        result=attempt.result,
        exam=exam,
        questions=questions,
        detailed_responses=detailed_responses
    )
