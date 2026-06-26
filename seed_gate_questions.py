import json
from datetime import datetime, timedelta
from app import create_app
from database.connection import db
from models.user import User
from models.exam import Subject, Exam, Question, Option
import os

def seed_database():
    app = create_app()
    with app.app_context():
        print("Checking for default admin user...")
        admin_user = User.query.filter_by(email='admin@example.com').first()
        if not admin_user:
            print("Admin user not found, seeding database first...")
            # Let's let app.py initialize it or create one
            admin_user = User(email='admin@example.com', role='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: admin@example.com / admin123")
        
        # Load questions from JSON
        json_path = os.path.join('database', 'gate_questions.json')
        if not os.path.exists(json_path):
            print(f"Error: {json_path} not found. Run generate_questions.py first.")
            return
            
        with open(json_path, 'r') as f:
            gate_questions = json.load(f)
            
        print(f"Loaded {len(gate_questions)} questions from {json_path}")
        
        # Cap to only the first 20 questions
        gate_questions = gate_questions[:20]
        print(f"Capped GATE questions to first {len(gate_questions)} questions.")
        
        # Create a single subject for the master exam
        subject_name = "GATE Computer Science"
        subject_code = "GATE_CS"
        
        subject = Subject.query.filter_by(code=subject_code).first()
        if not subject:
            subject = Subject(
                name=subject_name,
                code=subject_code,
                description="Comprehensive Graduate Aptitude Test in Engineering - Computer Science and Information Technology"
            )
            db.session.add(subject)
            db.session.flush()
            print(f"Created Subject: {subject_name} ({subject_code})")
        else:
            print(f"Subject already exists: {subject_name}")
            
        # Check if the master exam already exists
        exam_title = "GATE CS Complete Master Mock Exam"
        exam = Exam.query.filter_by(title=exam_title, subject_id=subject.id).first()
        
        # Compute total marks
        total_marks = sum(q['marks'] for q in gate_questions)
        description_text = "A comprehensive full-length 20-question practice exam covering the entire GATE Computer Science syllabus including Core CS subjects, Engineering Mathematics, Discrete Mathematics, and General Aptitude."
        
        if not exam:
            exam = Exam(
                subject_id=subject.id,
                title=exam_title,
                description=description_text,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() + timedelta(days=365),
                duration_minutes=180,
                total_marks=total_marks,
                passing_marks=int(total_marks * 0.33), # approx 33% passing
                negative_marking_val=0.33,
                created_by=admin_user.id
            )
            db.session.add(exam)
            db.session.flush()
            print(f"Created Exam: {exam_title} with total marks: {total_marks}")
        else:
            print(f"Exam already exists: {exam_title}. Updating details and clearing old questions...")
            exam.total_marks = total_marks
            exam.passing_marks = int(total_marks * 0.33)
            exam.description = description_text
            # Clear old questions to avoid duplication
            print("Clearing old questions for this exam to ensure clean seed...")
            Question.query.filter_by(exam_id=exam.id).delete()
            db.session.flush()
            
        # Add questions and options
        print("Inserting questions and options...")
        questions_inserted = 0
        options_inserted = 0
        
        for q_data in gate_questions:
            # Create question
            q_text_formatted = f"[{q_data['subject']}] {q_data['question']}\n\nExplanation: {q_data['explanation']}"
            
            question = Question(
                exam_id=exam.id,
                question_text=q_text_formatted,
                question_type='single',
                difficulty=q_data['difficulty'].lower(),
                marks=q_data['marks'],
                negative_marks=q_data['negative_marks']
            )
            db.session.add(question)
            db.session.flush()
            questions_inserted += 1
            
            # Create options
            for opt_key, opt_text in q_data['options'].items():
                is_correct = (opt_key == q_data['correct_answer'])
                option = Option(
                    question_id=question.id,
                    option_text=f"({opt_key}) {opt_text}",
                    is_correct=is_correct
                )
                db.session.add(option)
                options_inserted += 1
                
        db.session.commit()
        print("Database transaction committed successfully!")
        print(f"Total Questions Inserted: {questions_inserted}")
        print(f"Total Options Inserted: {options_inserted}")
        print("Seeding completed successfully!")

if __name__ == '__main__':
    seed_database()
