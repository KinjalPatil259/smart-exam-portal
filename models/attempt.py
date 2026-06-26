from database.connection import db
from datetime import datetime

class StudentExam(db.Model):
    __tablename__ = 'student_exam'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Numeric(6, 2), default=0.00)
    is_passed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='in_progress')  # 'in_progress', 'submitted', 'expired'
    
    # Relationships
    responses = db.relationship('StudentResponse', backref='attempt', cascade="all, delete-orphan")
    result = db.relationship('Result', backref='attempt', uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        db.Index('idx_attempt_student_exam', 'student_id', 'exam_id'),
    )


class StudentResponse(db.Model):
    __tablename__ = 'student_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    student_exam_id = db.Column(db.Integer, db.ForeignKey('student_exam.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('options.id', ondelete='CASCADE'), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('student_exam_id', 'question_id', 'option_id', name='uniq_response'),
    )


class Result(db.Model):
    __tablename__ = 'results'
    
    id = db.Column(db.Integer, primary_key=True)
    student_exam_id = db.Column(db.Integer, db.ForeignKey('student_exam.id', ondelete='CASCADE'), unique=True, nullable=False)
    score = db.Column(db.Numeric(6, 2), nullable=False)
    percentage = db.Column(db.Numeric(5, 2), nullable=False)
    passed = db.Column(db.Boolean, nullable=False)
    grade = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
