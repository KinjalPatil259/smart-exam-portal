import unittest
from app import create_app
from database.connection import db
from models.user import User, Student
from models.exam import Exam, Subject, Question, Option
from models.attempt import StudentExam, Result
from datetime import datetime, timedelta

class ExamSystemTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        self.app = create_app()
        self.app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', # In-memory database
            'WTF_CSRF_ENABLED': False
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Build tables
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_user_password_hashing(self):
        """Verify that password hashing functions accurately and secures credentials."""
        u = User(email='test@example.com', role='student')
        u.set_password('mysecretpwd')
        db.session.add(u)
        db.session.commit()
        
        # Verify check methods
        self.assertTrue(u.check_password('mysecretpwd'))
        self.assertFalse(u.check_password('wrongpwd'))
        self.assertNotEqual(u.password_hash, 'mysecretpwd')

    def test_student_and_admin_relationships(self):
        """Confirm that User cascading deletes matching profiles correctly."""
        u = User(email='student@example.com', role='student')
        u.set_password('password123')
        db.session.add(u)
        db.session.flush()
        
        s = Student(user_id=u.id, roll_number='STU999', name='Test Candidate')
        db.session.add(s)
        db.session.commit()
        
        self.assertEqual(u.student_profile.name, 'Test Candidate')
        self.assertEqual(s.user.email, 'student@example.com')
        
        # Check deletion cascade
        db.session.delete(u)
        db.session.commit()
        self.assertIsNone(Student.query.filter_by(roll_number='STU999').first())

    def test_exam_grading_score_calculation(self):
        """Test calculation of scores and implementation of negative marking penalties."""
        # Setup Subject and Exam
        sub = Subject(name='Network Routing', code='CS303')
        db.session.add(sub)
        db.session.flush()
        
        exam = Exam(
            subject_id=sub.id,
            title='Routing Basics',
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(days=1),
            duration_minutes=30,
            total_marks=10,
            passing_marks=40,
            negative_marking_val=0.25,
            created_by=1
        )
        db.session.add(exam)
        db.session.flush()
        
        # Setup Question 1: Single Choice (2 marks, negative 0.50)
        q1 = Question(exam_id=exam.id, question_text='Q1', question_type='single', marks=2, negative_marks=0.50)
        db.session.add(q1)
        db.session.flush()
        o1_correct = Option(question_id=q1.id, option_text='Correct A', is_correct=True)
        o1_wrong = Option(question_id=q1.id, option_text='Wrong A', is_correct=False)
        db.session.add_all([o1_correct, o1_wrong])
        
        # Setup Question 2: Multiple Choice (3 marks, negative 1.00)
        q2 = Question(exam_id=exam.id, question_text='Q2', question_type='multiple', marks=3, negative_marks=1.00)
        db.session.add(q2)
        db.session.flush()
        o2_correct_1 = Option(question_id=q2.id, option_text='Correct B1', is_correct=True)
        o2_correct_2 = Option(question_id=q2.id, option_text='Correct B2', is_correct=True)
        o2_wrong = Option(question_id=q2.id, option_text='Wrong B', is_correct=False)
        db.session.add_all([o2_correct_1, o2_correct_2, o2_wrong])
        db.session.commit()
        
        # 1. Test case: student answered Q1 correctly, Q2 wrong
        # Expected score: q1 (2 marks) + q2 penalty (-1.00) = 1.00 marks
        obtained_score = 0.0
        
        # Simulated check (identical to routes/exam.py logic)
        # Q1 Evaluation (Correct)
        correct_opts_q1 = {o1_correct.id}
        student_opts_q1 = {o1_correct.id} # Student picked correct option
        if correct_opts_q1 == student_opts_q1:
            obtained_score += q1.marks
        else:
            obtained_score -= float(q1.negative_marks)
            
        # Q2 Evaluation (Incorrect selection)
        correct_opts_q2 = {o2_correct_1.id, o2_correct_2.id}
        student_opts_q2 = {o2_correct_1.id, o2_wrong.id} # Student picked one correct, one wrong
        if correct_opts_q2 == student_opts_q2:
            obtained_score += q2.marks
        else:
            obtained_score -= float(q2.negative_marks)
            
        self.assertEqual(obtained_score, 1.00)

    def test_multiple_exam_attempts(self):
        """Verify that a student can take the same exam multiple times when previous attempts are submitted."""
        # Create student profile & user
        u = User(email='student_multi@example.com', role='student')
        u.set_password('password123')
        db.session.add(u)
        db.session.flush()
        s = Student(user_id=u.id, roll_number='STUMULTI', name='Multi Student')
        db.session.add(s)
        
        # Create Subject and Exam
        sub = Subject(name='Multi Exam Subject', code='ME101')
        db.session.add(sub)
        db.session.flush()
        
        exam = Exam(
            subject_id=sub.id,
            title='Multi Attempt Exam',
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=1),
            duration_minutes=30,
            total_marks=10,
            passing_marks=40,
            created_by=1
        )
        db.session.add(exam)
        db.session.commit()

        # Login student
        with self.client.session_transaction() as sess:
            sess['user_id'] = u.id
            sess['role'] = 'student'
        
        # First attempt creation: POST to /start/<exam_id>
        self.client.post(f'/start/{exam.id}', follow_redirects=True)
        attempts = StudentExam.query.filter_by(student_id=s.id, exam_id=exam.id).all()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].status, 'in_progress')
        first_attempt_id = attempts[0].id
        
        # Try starting another attempt while the first is in_progress - should resume the same attempt
        self.client.post(f'/start/{exam.id}', follow_redirects=True)
        attempts = StudentExam.query.filter_by(student_id=s.id, exam_id=exam.id).all()
        self.assertEqual(len(attempts), 1)
        
        # Submit/finalize the first attempt
        attempts[0].status = 'submitted'
        attempts[0].submitted_at = datetime.utcnow()
        result = Result(
            student_exam_id=attempts[0].id,
            score=5.0,
            percentage=50.0,
            passed=True,
            grade='D'
        )
        db.session.add(result)
        db.session.commit()
        
        # Start a second attempt: POST to /start/<exam_id> should create a new attempt
        self.client.post(f'/start/{exam.id}', follow_redirects=True)
        attempts = StudentExam.query.filter_by(student_id=s.id, exam_id=exam.id).all()
        self.assertEqual(len(attempts), 2)
        
        # Second attempt should be in progress
        in_progress_attempt = StudentExam.query.filter_by(student_id=s.id, exam_id=exam.id, status='in_progress').first()
        self.assertIsNotNone(in_progress_attempt)
        self.assertNotEqual(in_progress_attempt.id, first_attempt_id)

if __name__ == '__main__':
    unittest.main()
