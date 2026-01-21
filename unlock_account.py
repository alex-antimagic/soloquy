#!/usr/bin/env python3
"""
Unlock user account - works with both local and production databases
Usage:
  Local:      python3 unlock_account.py
  Production: heroku run python3 unlock_account.py -a worklead

You can also pass email as command line argument:
  python3 unlock_account.py user@example.com
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User

def unlock_account(email):
    """Unlock a user account"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False

        # Check if account is locked
        if user.is_account_locked():
            print(f"🔒 Account was locked until: {user.account_locked_until}")
            user.unlock_account()
            print(f"✅ Account unlocked successfully for {email}")
        else:
            print(f"ℹ️  Account for {email} was not locked")
            # Clear the field anyway to be sure
            user.account_locked_until = None
            db.session.commit()
            print(f"✅ Ensured account is unlocked")

        print(f"\n   User: {user.full_name}")
        print(f"   Email: {user.email}")
        print(f"   Status: Active and Unlocked")

        return True

if __name__ == '__main__':
    # Check for command line argument
    if len(sys.argv) >= 2:
        email = sys.argv[1]
    else:
        email = "support@antimagic.com"

    unlock_account(email)
