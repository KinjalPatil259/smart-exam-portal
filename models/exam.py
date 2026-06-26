from database.connection import db
from datetime import datetime

class Subject(db.Model):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    code = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    
    # Relationships
    exams = db.relationship('Exam', backref='subject', cascade="all, delete-orphan")


class Exam(db.Model):
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    total_marks = db.Column(db.Integer, default=100, nullable=False)
    passing_marks = db.Column(db.Integer, default=40, nullable=False)
    negative_marking_val = db.Column(db.Numeric(4, 2), default=0.00)
    random_questions_count = db.Column(db.Integer, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    questions = db.relationship('Question', backref='exam', cascade="all, delete-orphan")
    attempts = db.relationship('StudentExam', backref='exam', cascade="all, delete-orphan")
    
    # Composite Index
    __table_args__ = (
        db.Index('idx_exam_dates', 'start_time', 'end_time'),
    )


class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), default='single')  # 'single' or 'multiple'
    difficulty = db.Column(db.String(50), default='medium')  # 'easy', 'medium', 'hard'
    marks = db.Column(db.Integer, default=1)
    negative_marks = db.Column(db.Numeric(4, 2), default=0.00)
    
    # Relationships
    options = db.relationship('Option', backref='question', cascade="all, delete-orphan")
    responses = db.relationship('StudentResponse', backref='question', cascade="all, delete-orphan")


class Option(db.Model):
    __tablename__ = 'options'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    
    # Relationships
    responses = db.relationship('StudentResponse', backref='option', cascade="all, delete-orphan")
