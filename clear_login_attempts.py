#!/usr/bin/env python3
"""
Clear failed login attempts for a user - works with both local and production databases
Usage:
  Local:      python3 clear_login_attempts.py
  Production: heroku run python3 clear_login_attempts.py -a worklead

You can also pass email as command line argument:
  python3 clear_login_attempts.py user@example.com
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.audit_log import AuditLog

def clear_login_attempts(email):
    """Clear all failed login attempts for a user"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False

        # Get failed login attempts count before clearing
        failed_attempts = AuditLog.get_failed_login_attempts(user.id)

        print(f"Current status for {email} (User ID: {user.id}):")
        print(f"  - Failed login attempts in last hour: {failed_attempts}")
        print(f"  - Account locked: {user.is_account_locked()}")
        print(f"  - Account active: {user.is_active}")

        # Clear all failed login attempts for this user
        AuditLog.query.filter_by(
            user_id=user.id,
            event_type='login_attempt',
            event_status='failure'
        ).delete()

        # Ensure account is unlocked
        user.account_locked_until = None
        user.is_active = True

        db.session.commit()

        print(f"\n✅ Cleared all failed login attempts!")
        print(f"✅ Account unlocked and ready to use!")

        # Verify
        new_failed_attempts = AuditLog.get_failed_login_attempts(user.id)
        print(f"\nVerification:")
        print(f"  - Failed login attempts now: {new_failed_attempts}")
        print(f"  - Account locked: {user.is_account_locked()}")
        print(f"  - Status: READY TO LOGIN ✅")

        print(f"\n📋 Login Credentials:")
        print(f"   Email: {user.email}")
        print(f"   Password: Test123!")
        print(f"\nYou can now log in at: https://worklead.ai/login")

        return True

if __name__ == '__main__':
    # Check for command line argument
    if len(sys.argv) >= 2:
        email = sys.argv[1]
    else:
        email = "support@antimagic.com"

    clear_login_attempts(email)
