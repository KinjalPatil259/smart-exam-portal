from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app
from database.connection import db
from models.user import User, Student, Admin
from models.exam import Exam, Subject, Question, Option
from models.attempt import StudentExam, Result
from models.logger import Announcement, SystemLog
from routes.auth import admin_required
from routes import log_action
from sqlalchemy import func
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Admin Stats Calculations
    total_students = Student.query.count()
    total_subjects = Subject.query.count()
    total_exams = Exam.query.count()
    
    # Average Passing Rate
    total_results = Result.query.count()
    passed_results = Result.query.filter_by(passed=True).count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0.0
    
    # Active ongoing exams right now
    now = datetime.utcnow()
    active_exams_count = Exam.query.filter(Exam.start_time <= now, Exam.end_time >= now).count()
    
    # Recent logs
    recent_logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(6).all()
    
    # Recent announcements
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    
    # Subject-wise pass distribution for Chart.js
    subject_exam_stats = db.session.query(
        Subject.name,
        func.count(Result.id),
        func.sum(func.cast(Result.passed, db.Integer))
    ).join(Exam, Exam.subject_id == Subject.id)\
     .join(StudentExam, StudentExam.exam_id == Exam.id)\
     .join(Result, Result.student_exam_id == StudentExam.id)\
     .group_by(Subject.name).all()
     
    chart_subjects = [row[0] for row in subject_exam_stats]
    chart_attempts = [int(row[1]) for row in subject_exam_stats]
    chart_passes = [int(row[2]) if row[2] else 0 for row in subject_exam_stats]
    
    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        total_subjects=total_subjects,
        total_exams=total_exams,
        pass_rate=round(pass_rate, 1),
        active_exams_count=active_exams_count,
        recent_logs=recent_logs,
        announcements=announcements,
        chart_subjects=chart_subjects,
        chart_attempts=chart_attempts,
        chart_passes=chart_passes
    )

# ----------------- Student Management CRUD -----------------
@admin_bp.route('/students', methods=['GET', 'POST'])
@admin_required
def students():
    if request.method == 'POST':
        # Add new student
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip().upper()
        password = request.form.get('password', '')
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not email or not name or not roll_number or not password:
            flash('All marked fields are required.', 'danger')
            return redirect(url_for('admin.students'))
            
        if User.query.filter_by(email=email).first() or Student.query.filter_by(roll_number=roll_number).first():
            flash('Email or Roll number already exists.', 'danger')
            return redirect(url_for('admin.students'))
            
        try:
            u = User(email=email, role='student')
            u.set_password(password)
            db.session.add(u)
            db.session.flush()
            
            s = Student(user_id=u.id, roll_number=roll_number, name=name, department=department, phone=phone)
            db.session.add(s)
            db.session.commit()
            
            log_action("Admin Created Student", f"Created student {name} ({roll_number})")
            flash(f"Student {name} created successfully.", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Student creation error: {e}")
            flash('Error creating student.', 'danger')
            
        return redirect(url_for('admin.students'))
        
    all_students = Student.query.all()
    return render_template('admin/students.html', students=all_students)


@admin_bp.route('/student/toggle/<int:user_id>', methods=['POST'])
@admin_required
def toggle_student(user_id):
    user = db.session.get(User, user_id)
    if user and user.role == 'student':
        user.status = 'inactive' if user.status == 'active' else 'active'
        db.session.commit()
        log_action("Admin Toggled Student Status", f"Set User ID {user.id} status to {user.status}")
        flash(f"Student status updated to {user.status}.", 'success')
    return redirect(url_for('admin.students'))


@admin_bp.route('/student/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_student(user_id):
    user = db.session.get(User, user_id)
    if user and user.role == 'student':
        log_action("Admin Deleted Student", f"Deleted Student: {user.student_profile.name if user.student_profile else user.email}")
        db.session.delete(user)
        db.session.commit()
        flash('Student deleted successfully.', 'success')
    return redirect(url_for('admin.students'))


# ----------------- Subject Management CRUD -----------------
@admin_bp.route('/subjects', methods=['GET', 'POST'])
@admin_required
def subjects():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip().upper()
        description = request.form.get('description', '').strip()
        
        if not name or not code:
            flash('Subject Name and Code are required.', 'danger')
            return redirect(url_for('admin.subjects'))
            
        if Subject.query.filter((Subject.name == name) | (Subject.code == code)).first():
            flash('Subject Code or Name already exists.', 'danger')
            return redirect(url_for('admin.subjects'))
            
        try:
            sub = Subject(name=name, code=code, description=description)
            db.session.add(sub)
            db.session.commit()
            log_action("Admin Created Subject", f"Created subject: {name} ({code})")
            flash('Subject created successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error creating subject.', 'danger')
            
        return redirect(url_for('admin.subjects'))
        
    all_subjects = Subject.query.all()
    return render_template('admin/subjects.html', subjects=all_subjects)


@admin_bp.route('/subject/edit/<int:subject_id>', methods=['POST'])
@admin_required
def edit_subject(subject_id):
    sub = db.session.get(Subject, subject_id)
    if sub:
        sub.name = request.form.get('name', '').strip()
        sub.code = request.form.get('code', '').strip().upper()
        sub.description = request.form.get('description', '').strip()
        try:
            db.session.commit()
            log_action("Admin Edited Subject", f"Updated subject: {sub.name}")
            flash('Subject updated successfully.', 'success')
        except Exception:
            db.session.rollback()
            flash('Failed to update subject details. Name or code may already exist.', 'danger')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subject/delete/<int:subject_id>', methods=['POST'])
@admin_required
def delete_subject(subject_id):
    sub = db.session.get(Subject, subject_id)
    if sub:
        log_action("Admin Deleted Subject", f"Deleted subject: {sub.name} ({sub.code})")
        db.session.delete(sub)
        db.session.commit()
        flash('Subject and associated exams deleted.', 'success')
    return redirect(url_for('admin.subjects'))


# ----------------- Exam Management CRUD -----------------
@admin_bp.route('/exams', methods=['GET', 'POST'])
@admin_required
def exams():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        duration = request.form.get('duration')
        total_marks = request.form.get('total_marks')
        passing_marks = request.form.get('passing_marks')
        negative_val = request.form.get('negative_marking_val', '0.00')
        random_count = request.form.get('random_questions_count')
        
        # Validations
        if not subject_id or not title or not start_time_str or not end_time_str or not duration:
            flash('Please populate all required fields.', 'danger')
            return redirect(url_for('admin.exams'))
            
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            
            if start_time >= end_time:
                flash('End time must be after the start time.', 'danger')
                return redirect(url_for('admin.exams'))
                
            exam = Exam(
                subject_id=int(subject_id),
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=int(duration),
                total_marks=int(total_marks) if total_marks else 100,
                passing_marks=int(passing_marks) if passing_marks else 40,
                negative_marking_val=float(negative_val),
                random_questions_count=int(random_count) if random_count else None,
                created_by=g.user.id
            )
            db.session.add(exam)
            db.session.commit()
            
            log_action("Admin Created Exam", f"Created exam: {title}")
            flash('Exam scheduled successfully. Now you can add questions.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Exam creation error: {e}")
            flash('Error adding exam. Verify format settings.', 'danger')
            
        return redirect(url_for('admin.exams'))
        
    all_exams = Exam.query.order_by(Exam.start_time.desc()).all()
    all_subjects = Subject.query.all()
    return render_template('admin/exams.html', exams=all_exams, subjects=all_subjects)


@admin_bp.route('/exam/edit/<int:exam_id>', methods=['POST'])
@admin_required
def edit_exam(exam_id):
    exam = db.session.get(Exam, exam_id)
    if exam:
        exam.title = request.form.get('title', '').strip()
        exam.description = request.form.get('description', '').strip()
        exam.duration_minutes = int(request.form.get('duration'))
        exam.total_marks = int(request.form.get('total_marks'))
        exam.passing_marks = int(request.form.get('passing_marks'))
        exam.negative_marking_val = float(request.form.get('negative_marking_val', '0.00'))
        
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        
        random_count = request.form.get('random_questions_count')
        exam.random_questions_count = int(random_count) if random_count else None
        
        try:
            exam.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            exam.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            db.session.commit()
            log_action("Admin Edited Exam", f"Updated exam settings for: {exam.title}")
            flash('Exam parameters modified.', 'success')
        except Exception:
            db.session.rollback()
            flash('Error editing exam scheduling.', 'danger')
            
    return redirect(url_for('admin.exams'))


@admin_bp.route('/exam/delete/<int:exam_id>', methods=['POST'])
@admin_required
def delete_exam(exam_id):
    exam = db.session.get(Exam, exam_id)
    if exam:
        log_action("Admin Deleted Exam", f"Deleted exam: {exam.title}")
        db.session.delete(exam)
        db.session.commit()
        flash('Exam deleted successfully.', 'success')
    return redirect(url_for('admin.exams'))


# ----------------- Question Bank & Options CRUD -----------------
@admin_bp.route('/exam/<int:exam_id>/questions', methods=['GET', 'POST'])
@admin_required
def questions(exam_id):
    exam = db.session.get(Exam, exam_id)
    if not exam:
        flash('Exam not found.', 'danger')
        return redirect(url_for('admin.exams'))
        
    if request.method == 'POST':
        question_text = request.form.get('question_text', '').strip()
        question_type = request.form.get('question_type', 'single')
        difficulty = request.form.get('difficulty', 'medium')
        marks = int(request.form.get('marks', 1))
        neg_marks = float(request.form.get('negative_marks', 0.00))
        
        # Options list
        opt_texts = request.form.getlist('options[]')
        correct_indices = request.form.getlist('correct_options[]') # String representation of indices e.g., '0', '1'
        
        if not question_text or len(opt_texts) < 2:
            flash('Please enter a question and at least 2 options.', 'danger')
            return redirect(url_for('admin.questions', exam_id=exam.id))
            
        try:
            # Create question
            q = Question(
                exam_id=exam.id,
                question_text=question_text,
                question_type=question_type,
                difficulty=difficulty,
                marks=marks,
                negative_marks=neg_marks
            )
            db.session.add(q)
            db.session.flush() # Populate ID
            
            # Create options
            for idx, text in enumerate(opt_texts):
                if text.strip() == '': continue
                is_correct = str(idx) in correct_indices
                opt = Option(
                    question_id=q.id,
                    option_text=text.strip(),
                    is_correct=is_correct
                )
                db.session.add(opt)
                
            db.session.commit()
            log_action("Admin Added Question", f"Added question to exam '{exam.title}'")
            flash('Question added to exam question bank.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding question: {e}")
            flash('Failed to save question.', 'danger')
            
        return redirect(url_for('admin.questions', exam_id=exam.id))
        
    return render_template('admin/questions.html', exam=exam)


@admin_bp.route('/question/delete/<int:q_id>', methods=['POST'])
@admin_required
def delete_question(q_id):
    q = db.session.get(Question, q_id)
    if q:
        exam_id = q.exam_id
        log_action("Admin Deleted Question", f"Removed question from exam ID {exam_id}")
        db.session.delete(q)
        db.session.commit()
        flash('Question removed.', 'success')
        return redirect(url_for('admin.questions', exam_id=exam_id))
    return redirect(url_for('admin.exams'))


# ----------------- Announcement & System settings -----------------
@admin_bp.route('/announcement/add', methods=['POST'])
@admin_required
def add_announcement():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if title and content:
        a = Announcement(title=title, content=content, created_by=g.user.id)
        db.session.add(a)
        db.session.commit()
        log_action("Admin Created Announcement", f"Title: {title}")
        flash('Announcement posted successfully.', 'success')
    else:
        flash('All announcement fields required.', 'danger')
        
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/announcement/delete/<int:a_id>', methods=['POST'])
@admin_required
def delete_announcement(a_id):
    a = db.session.get(Announcement, a_id)
    if a:
        db.session.delete(a)
        db.session.commit()
        flash('Announcement removed.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/logs')
@admin_required
def logs():
    # Filter operations or pagination
    search = request.args.get('search', '')
    
    query = SystemLog.query.order_by(SystemLog.timestamp.desc())
    if search:
        query = query.filter(
            SystemLog.action.like(f"%{search}%") | 
            SystemLog.details.like(f"%{search}%") |
            SystemLog.ip_address.like(f"%{search}%")
        )
        
    system_logs = query.all()
    return render_template('admin/logs.html', logs=system_logs, search=search)


@admin_bp.route('/reports')
@admin_required
def reports():
    exams = Exam.query.all()
    return render_template('admin/reports.html', exams=exams)
