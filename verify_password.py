#!/usr/bin/env python3
"""
Verify password for a user
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User

def verify_password(email, test_password):
    """Verify if password is correct"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False

        print(f"Testing password for {email}...")
        print(f"Test password: '{test_password}'")

        # Check password
        is_correct = user.check_password(test_password)

        if is_correct:
            print(f"\n✅ Password is CORRECT!")
            print(f"   You can log in with:")
            print(f"   Email: {email}")
            print(f"   Password: {test_password}")
        else:
            print(f"\n❌ Password is INCORRECT!")
            print(f"   The stored password hash does NOT match '{test_password}'")
            print(f"\n   Resetting password to '{test_password}'...")
            user.set_password(test_password)
            db.session.commit()
            print(f"   ✅ Password has been reset!")

        return is_correct

if __name__ == '__main__':
    email = "support@antimagic.com"
    password = "Test123!"

    verify_password(email, password)
