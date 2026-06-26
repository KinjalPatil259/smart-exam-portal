import os
import functools
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, g, current_app
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from database.connection import db
from models.user import User, Student, Admin
from routes import log_action

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Hydrate global request context
        user = db.session.get(User, session['user_id'])
        if not user or user.status != 'active':
            session.clear()
            flash('Your account has been deactivated or not found.', 'danger')
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Unauthorized access. Admin privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        
        user = db.session.get(User, session['user_id'])
        if not user or user.status != 'active':
            session.clear()
            flash('Your account has been deactivated.', 'danger')
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.app_context_processor
def inject_user():
    """Exposes g.user dynamically to jinja templates as current_user."""
    user = None
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
    return dict(current_user=user)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('admin.dashboard' if session.get('role') == 'admin' else 'student.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip().upper()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        bio = request.form.get('bio', '').strip()
        
        # Security validation
        if not email or not name or not roll_number or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('auth/register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
            
        # Check unique constraints
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')
            
        if Student.query.filter_by(roll_number=roll_number).first():
            flash('Roll number already exists.', 'danger')
            return render_template('auth/register.html')
            
        try:
            # Create user account
            new_user = User(email=email, role='student')
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush() # Fetch generated ID
            
            # Create student profile
            new_student = Student(
                user_id=new_user.id,
                roll_number=roll_number,
                name=name,
                phone=phone,
                department=department,
                bio=bio
            )
            db.session.add(new_student)
            db.session.commit()
            
            log_action("User Registered", f"Student profile created for {name} ({roll_number})", user_id=new_user.id)
            
            # Log in automatically
            session['user_id'] = new_user.id
            session['role'] = 'student'
            session['name'] = name
            
            flash('Registration successful! Welcome to the Smart Online Exam system.', 'success')
            return redirect(url_for('student.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration failure: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')
            
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin.dashboard' if session.get('role') == 'admin' else 'student.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('auth/login.html')
            
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if user.status != 'active':
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return render_template('auth/login.html')
                
            session['user_id'] = user.id
            session['role'] = user.role
            
            if user.role == 'admin':
                session['name'] = user.admin_profile.name if user.admin_profile else 'Administrator'
                log_action("Admin Login", "Successful administrator login", user_id=user.id)
                flash('Logged in successfully as Administrator.', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                session['name'] = user.student_profile.name if user.student_profile else 'Student'
                log_action("Student Login", "Successful student login", user_id=user.id)
                flash('Logged in successfully.', 'success')
                return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    if 'user_id' in session:
        log_action("User Logout", "User logged out of session")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    student = g.user.student_profile
    admin = g.user.admin_profile
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        bio = request.form.get('bio', '').strip()
        
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not name:
            flash('Name is required.', 'danger')
            return redirect(url_for('auth.profile'))
            
        # Update user profiles
        try:
            if g.user.role == 'student' and student:
                student.name = name
                student.phone = phone
                student.department = department
                student.bio = bio
                session['name'] = name
                
                # Check for profile image upload
                if 'avatar' in request.files:
                    file = request.files['avatar']
                    if file and file.filename != '' and allowed_file(file.filename):
                        filename = secure_filename(f"avatar_{g.user.id}_{file.filename}")
                        # Create folders if not exists
                        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'avatars')
                        os.makedirs(upload_path, exist_ok=True)
                        file_dest = os.path.join(upload_path, filename)
                        file.save(file_dest)
                        student.avatar_url = f"uploads/avatars/{filename}"
                        
            elif g.user.role == 'admin' and admin:
                admin.name = name
                admin.department = department
                session['name'] = name
                
            # If changing password
            if new_password:
                if new_password != confirm_password:
                    flash('New passwords do not match.', 'danger')
                    return redirect(url_for('auth.profile'))
                g.user.set_password(new_password)
                
            db.session.commit()
            log_action("Profile Update", "Successfully updated profile information")
            flash('Profile updated successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Profile update failure: {e}")
            flash('An error occurred. Profile could not be updated.', 'danger')
            
        return redirect(url_for('auth.profile'))
        
    return render_template('student/profile.html' if g.user.role == 'student' else 'admin/settings.html', student=student, admin=admin)
