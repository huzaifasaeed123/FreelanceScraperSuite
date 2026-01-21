"""
Authentication Module
Handles user authentication and session management
"""

from functools import wraps
from flask import session, redirect, url_for, request
from database.models import DatabaseManager
import os


def init_admin_user():
    """Initialize admin user from environment variables if not exists"""
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@insurance.com')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    admin_name = os.getenv('ADMIN_NAME', 'Admin')

    # Check if admin exists
    existing_admin = DatabaseManager.get_user_by_email(admin_email)
    if not existing_admin:
        user_id = DatabaseManager.create_user(
            name=admin_name,
            email=admin_email,
            password=admin_password,
            is_admin=True
        )
        if user_id:
            print(f"Admin user created: {admin_email}")
        else:
            print(f"Failed to create admin user")
    else:
        print(f"Admin user already exists: {admin_email}")


def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin', False):
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get current logged-in user data"""
    if 'user_id' in session:
        return {
            'id': session['user_id'],
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'is_admin': session.get('is_admin', False)
        }
    return None


def login_user(user_data):
    """Set session data for logged-in user"""
    session['user_id'] = user_data['id']
    session['user_name'] = user_data['name']
    session['user_email'] = user_data['email']
    session['is_admin'] = user_data.get('is_admin', False)


def logout_user():
    """Clear session data for logged-out user"""
    session.clear()
