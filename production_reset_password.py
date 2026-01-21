#!/usr/bin/env python3
"""
Reset user password - works with both local and production databases
Usage:
  Local:      python3 production_reset_password.py
  Production: heroku run python3 production_reset_password.py -a worklead
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User

def reset_password(email, new_password):
    """Reset password for a user"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False

        # Reset password
        user.set_password(new_password)
        db.session.commit()

        print(f"✅ Password reset successfully for {email}")
        print(f"   User: {user.full_name}")
        print(f"   Email: {user.email}")
        print(f"   New password: {new_password}")

        return True

if __name__ == '__main__':
    email = "support@antimagic.com"
    password = "Test123!"

    reset_password(email, password)
