#!/usr/bin/env python3
"""
Force unlock user account and clear all lock-related fields
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from datetime import datetime

def force_unlock(email):
    """Force unlock a user account and verify"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False

        print(f"Current account status for {email}:")
        print(f"  - account_locked_until: {user.account_locked_until}")
        print(f"  - is_active: {user.is_active}")
        print(f"  - is_account_locked(): {user.is_account_locked()}")

        # Force unlock - set all lock-related fields to unlocked state
        user.account_locked_until = None
        user.is_active = True

        # Commit changes
        db.session.commit()

        # Verify unlock
        db.session.refresh(user)

        print(f"\n✅ Account forcefully unlocked!")
        print(f"\nVerification - New account status:")
        print(f"  - account_locked_until: {user.account_locked_until}")
        print(f"  - is_active: {user.is_active}")
        print(f"  - is_account_locked(): {user.is_account_locked()}")

        print(f"\n📋 Account Details:")
        print(f"   User: {user.full_name}")
        print(f"   Email: {user.email}")
        print(f"   Status: {'UNLOCKED ✅' if not user.is_account_locked() else 'STILL LOCKED ❌'}")

        return True

if __name__ == '__main__':
    email = "support@antimagic.com"
    force_unlock(email)
