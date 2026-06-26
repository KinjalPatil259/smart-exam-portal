from flask import session, request
from database.connection import db
from models.logger import SystemLog

def log_action(action, details=None, user_id=None):
    """Utility helper to log administrative and student activities in the audit log."""
    if not user_id:
        user_id = session.get('user_id')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    # Check if we are inside a Flask request context
    log_entry = SystemLog(
        user_id=user_id,
        action=action,
        ip_address=ip,
        details=details
    )
    db.session.add(log_entry)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error writing audit log: {e}")
