import os
from flask import Flask, render_template, session, redirect, url_for
from config import Config
from database.connection import db
from datetime import datetime, timedelta

# Import models to register on SQLAlchemy metadata
import models

# Import Blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.student import student_bp
from routes.exam import exam_bp
from routes.reports import reports_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Bind Database connection
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(reports_bp)
    
    # Define Public routes
    @app.route('/')
    def home():
        if 'user_id' in session:
            return redirect(url_for('admin.dashboard' if session.get('role') == 'admin' else 'student.dashboard'))
        return render_template('home.html')

    @app.route('/about')
    def about():
        return render_template('about.html')

    @app.route('/contact')
    def contact():
        return render_template('contact.html')
        
    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html'), 404
        
    # Initialize and Seed Database
    with app.app_context():
        # Creates database tables if not existing
        db.create_all()
        
        # Check and Seed Default Admin User
        admin_check = models.User.query.filter_by(email='admin@example.com').first()
        if not admin_check:
            try:
                # Create admin user record
                admin_user = models.User(email='admin@example.com', role='admin')
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                db.session.flush() # Fetch primary key ID
                
                # Create admin profile detail
                admin_profile = models.Admin(
                    user_id=admin_user.id,
                    employee_id='ADM1001',
                    name='System Administrator',
                    department='Examination Cell'
                )
                db.session.add(admin_profile)
                
                
                db.session.commit()
                print("Default Database Seeded Successfully.")
                print("Admin Account Created: email='admin@example.com', password='admin123'")
            except Exception as e:
                db.session.rollback()
                print(f"Error seeding database: {e}")
                
    return app

# Development Server Launcher
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
