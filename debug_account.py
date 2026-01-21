#!/usr/bin/env python3
"""
Debug account lock status and show all recent login attempts
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.audit_log import AuditLog

def debug_account(email):
    """Debug account lock status"""
    app = create_app()

    with app.app_context():
        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"❌ Error: User with email '{email}' not found")
            return False

        print(f"=== Account Debug for {email} (User ID: {user.id}) ===\n")

        print("User Model Fields:")
        print(f"  - is_active: {user.is_active}")
        print(f"  - account_locked_until: {user.account_locked_until}")
        print(f"  - is_account_locked(): {user.is_account_locked()}")

        # Check failed login attempts in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        failed_attempts = AuditLog.query.filter(
            AuditLog.user_id == user.id,
            AuditLog.event_type == 'login_attempt',
            AuditLog.event_status == 'failure',
            AuditLog.created_at >= one_hour_ago
        ).count()

        print(f"\nAudit Log:")
        print(f"  - Failed login attempts in last hour: {failed_attempts}")

        # Show all recent audit log entries
        print(f"\nRecent Audit Log Entries (last 24 hours):")
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_logs = AuditLog.query.filter(
            AuditLog.user_id == user.id,
            AuditLog.created_at >= yesterday
        ).order_by(AuditLog.created_at.desc()).limit(20).all()

        if recent_logs:
            for log in recent_logs:
                print(f"  - {log.created_at}: {log.event_type} - {log.event_status} - {log.details}")
        else:
            print("  - No recent entries")

        # Check should_lock_account
        print(f"\nLock Check:")
        should_lock = AuditLog.should_lock_account(user.id)
        print(f"  - AuditLog.should_lock_account(): {should_lock}")

        return True

if __name__ == '__main__':
    email = "support@antimagic.com"
    debug_account(email)
