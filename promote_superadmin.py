#!/usr/bin/env python
"""
Superadmin Promotion Script

Promotes a user to superadmin status for system administration access.

Usage:
    python promote_superadmin.py <email>

Example:
    python promote_superadmin.py alex@example.com

Or via Heroku:
    heroku run python promote_superadmin.py alex@example.com
"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.user import User


def promote_to_superadmin(email):
    """Promote a user to superadmin status"""
    app = create_app(os.getenv('FLASK_ENV', 'production'))

    with app.app_context():
        # Find user by email
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: No user found with email: {email}")
            print("\nAvailable users:")
            users = User.query.all()
            for u in users:
                superadmin_badge = " [SUPERADMIN]" if u.is_superadmin else ""
                print(f"  - {u.email}{superadmin_badge}")
            return False

        # Check if already superadmin
        if user.is_superadmin:
            print(f"ℹ️  User {email} is already a superadmin")
            return True

        # Promote to superadmin
        user.is_superadmin = True
        db.session.commit()

        print(f"✅ Successfully promoted {email} to superadmin!")
        print(f"\nUser Details:")
        print(f"  Email: {user.email}")
        print(f"  Name: {user.full_name}")
        print(f"  Superadmin: {user.is_superadmin}")
        print(f"\nThe user can now access the admin dashboard at /admin")

        return True


def revoke_superadmin(email):
    """Revoke superadmin status from a user"""
    app = create_app(os.getenv('FLASK_ENV', 'production'))

    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: No user found with email: {email}")
            return False

        if not user.is_superadmin:
            print(f"ℹ️  User {email} is not a superadmin")
            return True

        user.is_superadmin = False
        db.session.commit()

        print(f"✅ Successfully revoked superadmin status from {email}")
        return True


def list_superadmins():
    """List all current superadmins"""
    app = create_app(os.getenv('FLASK_ENV', 'production'))

    with app.app_context():
        superadmins = User.query.filter_by(is_superadmin=True).all()

        if not superadmins:
            print("No superadmins found.")
            return

        print(f"Current Superadmins ({len(superadmins)}):")
        print("-" * 60)
        for user in superadmins:
            print(f"  {user.email} ({user.full_name})")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Superadmin Management Script")
        print("=" * 60)
        print("\nUsage:")
        print("  Promote user:     python promote_superadmin.py <email>")
        print("  Revoke superadmin: python promote_superadmin.py --revoke <email>")
        print("  List superadmins:  python promote_superadmin.py --list")
        print("\nExamples:")
        print("  python promote_superadmin.py alex@example.com")
        print("  heroku run python promote_superadmin.py alex@example.com")
        print("  python promote_superadmin.py --list")
        sys.exit(1)

    if sys.argv[1] == '--list':
        list_superadmins()
    elif sys.argv[1] == '--revoke':
        if len(sys.argv) < 3:
            print("❌ Error: Email required for --revoke")
            sys.exit(1)
        revoke_superadmin(sys.argv[2])
    else:
        email = sys.argv[1]
        promote_to_superadmin(email)
