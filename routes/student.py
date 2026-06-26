from flask import Blueprint, render_template, session, redirect, url_for, flash, g
from database.connection import db
from models.user import Student
from models.exam import Exam, Subject
from models.attempt import StudentExam, Result
from models.logger import Announcement
from routes.auth import login_required
from sqlalchemy import func
from datetime import datetime

student_bp = Blueprint('student', __name__)

@student_bp.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('admin.dashboard'))
        
    student = g.user.student_profile
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.logout'))
        
    # Announcements
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
    
    # Available active exams: start_time <= now <= end_time
    now = datetime.utcnow()
    
    available_exams = Exam.query.filter(
        Exam.start_time <= now,
        Exam.end_time >= now
    ).all()
    
    # Recent attempts
    recent_attempts = StudentExam.query.filter_by(student_id=student.id)\
        .order_by(StudentExam.submitted_at.desc()).limit(5).all()
        
    # Performance analytics calculation
    # 1. Total exams attempted
    total_attempts = len(student.attempts)
    
    # 2. Passed exams count
    passed_count = sum(1 for a in student.attempts if a.is_passed and a.status == 'submitted')
    
    # 3. Average score percentage
    completed_results = Result.query.join(StudentExam).filter(StudentExam.student_id == student.id).all()
    avg_percentage = float(sum(r.percentage for r in completed_results) / len(completed_results)) if completed_results else 0.0
    
    # 4. Subject-wise performance metrics for Chart.js
    subject_stats = db.session.query(
        Subject.name,
        func.avg(Result.percentage)
    ).join(Exam, Exam.subject_id == Subject.id)\
     .join(StudentExam, StudentExam.exam_id == Exam.id)\
     .join(Result, Result.student_exam_id == StudentExam.id)\
     .filter(StudentExam.student_id == student.id)\
     .group_by(Subject.name).all()
     
    chart_subjects = [s[0] for s in subject_stats]
    chart_percentages = [float(s[1]) for s in subject_stats]

    # Leaderboard (Top 5 students by average percentage)
    leaderboard_query = db.session.query(
        Student.name,
        Student.roll_number,
        func.avg(Result.percentage).label('avg_pct')
    ).join(StudentExam, StudentExam.student_id == Student.id)\
     .join(Result, Result.student_exam_id == StudentExam.id)\
     .group_by(Student.id, Student.name, Student.roll_number)\
     .order_by(func.avg(Result.percentage).desc())\
     .limit(5).all()
     
    leaderboard = [
        {'name': row[0], 'roll_number': row[1], 'avg_pct': round(float(row[2]), 2)}
        for row in leaderboard_query
    ]
    
    return render_template(
        'student/dashboard.html',
        student=student,
        announcements=announcements,
        available_exams_count=len(available_exams),
        recent_attempts=recent_attempts,
        total_attempts=total_attempts,
        passed_count=passed_count,
        avg_percentage=round(avg_percentage, 1),
        chart_subjects=chart_subjects,
        chart_percentages=chart_percentages,
        leaderboard=leaderboard
    )


@student_bp.route('/exams')
@login_required
def available_exams():
    if session.get('role') != 'student':
        return redirect(url_for('admin.dashboard'))
        
    student = g.user.student_profile
    now = datetime.utcnow()
    
    # Get all active exams
    active_exams = Exam.query.filter(
        Exam.start_time <= now,
        Exam.end_time >= now
    ).order_by(Exam.start_time.asc()).all()
    
    # Build details for active exams, including in-progress and completed attempts
    active_exams_data = []
    for exam in active_exams:
        in_progress = StudentExam.query.filter_by(
            student_id=student.id,
            exam_id=exam.id,
            status='in_progress'
        ).first()
        
        completed = StudentExam.query.filter_by(
            student_id=student.id,
            exam_id=exam.id,
            status='submitted'
        ).order_by(StudentExam.submitted_at.desc()).all()
        
        active_exams_data.append({
            'exam': exam,
            'in_progress': in_progress,
            'completed': completed
        })
            
    # Upcoming exams (start_time > now)
    upcoming = Exam.query.filter(
        Exam.start_time > now
    ).order_by(Exam.start_time.asc()).all()
    
    return render_template(
        'student/available_exams.html',
        active_exams_data=active_exams_data,
        upcoming=upcoming
    )


@student_bp.route('/history')
@login_required
def history():
    if session.get('role') != 'student':
        return redirect(url_for('admin.dashboard'))
        
    student = g.user.student_profile
    attempts = StudentExam.query.filter_by(student_id=student.id)\
        .order_by(StudentExam.started_at.desc()).all()
        
    return render_template('student/history.html', attempts=attempts)
