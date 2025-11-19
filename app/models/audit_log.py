"""
Audit Log Model
Tracks security-sensitive events for compliance and investigation
"""
from datetime import datetime
from app import db
import json


class AuditLog(db.Model):
    """Audit log for security events and compliance tracking"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Event information
    event_type = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'mcp_start', 'integration_connect'
    event_status = db.Column(db.String(20), nullable=False, default='success')  # 'success', 'failure', 'denied'

    # Actor information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True, index=True)

    # Resource information
    resource_type = db.Column(db.String(50), nullable=True)  # 'integration', 'agent', 'mcp_server'
    resource_id = db.Column(db.Integer, nullable=True, index=True)

    # Request context
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.String(500), nullable=True)

    # Event details (JSON)
    details = db.Column(db.Text, nullable=True)  # JSON string with additional context

    # Error information (for failures)
    error_message = db.Column(db.Text, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id])
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id])
    agent = db.relationship('Agent', foreign_keys=[agent_id])

    def __repr__(self):
        return f'<AuditLog {self.event_type} - {self.created_at}>'

    def get_details(self):
        """Parse and return details as dict"""
        if self.details:
            try:
                return json.loads(self.details)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_details(self, details_dict):
        """Set details from dict"""
        if details_dict:
            self.details = json.dumps(details_dict)

    @staticmethod
    def log_mcp_access(user_id, tenant_id, agent_id, integration, status='success', error=None, ip_address=None):
        """
        Log MCP server access attempt

        Args:
            user_id: ID of user triggering the access
            tenant_id: ID of tenant
            agent_id: ID of agent accessing the integration
            integration: Integration object being accessed
            status: 'success' or 'denied'
            error: Optional error message
            ip_address: Optional IP address of request
        """
        details = {
            'integration_type': integration.integration_type,
            'owner_type': integration.owner_type,
            'owner_id': integration.owner_id,
            'integration_display_name': integration.display_name,
            'mcp_process_name': integration.get_mcp_process_name()
        }

        log = AuditLog(
            event_type='mcp_access',
            event_status=status,
            user_id=user_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            resource_type='integration',
            resource_id=integration.id,
            ip_address=ip_address,
            error_message=error
        )
        log.set_details(details)

        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def log_integration_connect(user_id, tenant_id, integration, ip_address=None, user_agent=None):
        """Log integration connection event"""
        details = {
            'integration_type': integration.integration_type,
            'owner_type': integration.owner_type,
            'owner_id': integration.owner_id,
            'display_name': integration.display_name
        }

        log = AuditLog(
            event_type='integration_connect',
            event_status='success',
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type='integration',
            resource_id=integration.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        log.set_details(details)

        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def log_integration_disconnect(user_id, tenant_id, integration, ip_address=None):
        """Log integration disconnection event"""
        details = {
            'integration_type': integration.integration_type,
            'owner_type': integration.owner_type,
            'owner_id': integration.owner_id,
            'display_name': integration.display_name
        }

        log = AuditLog(
            event_type='integration_disconnect',
            event_status='success',
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type='integration',
            resource_id=integration.id,
            ip_address=ip_address
        )
        log.set_details(details)

        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def log_access_denied(user_id, tenant_id, resource_type, resource_id, reason, agent_id=None, ip_address=None):
        """Log denied access attempt"""
        details = {
            'reason': reason,
            'resource_type': resource_type,
            'resource_id': resource_id
        }

        log = AuditLog(
            event_type='access_denied',
            event_status='denied',
            user_id=user_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            error_message=reason
        )
        log.set_details(details)

        db.session.add(log)
        db.session.commit()
        return log

    @classmethod
    def get_recent_for_tenant(cls, tenant_id, limit=100, event_type=None):
        """Get recent audit logs for a tenant"""
        query = cls.query.filter_by(tenant_id=tenant_id)

        if event_type:
            query = query.filter_by(event_type=event_type)

        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_suspicious_activity(cls, tenant_id, hours=24):
        """Get potentially suspicious activity in the last N hours"""
        from datetime import timedelta
        threshold = datetime.utcnow() - timedelta(hours=hours)

        return cls.query.filter(
            cls.tenant_id == tenant_id,
            cls.event_status.in_(['failure', 'denied']),
            cls.created_at >= threshold
        ).order_by(cls.created_at.desc()).all()

    @staticmethod
    def log_login_attempt(email, success=True, ip_address=None, user_agent=None, error_message=None):
        """
        Log login attempt (successful or failed)

        Args:
            email: Email address used in login attempt
            success: Whether login was successful
            ip_address: IP address of request
            user_agent: User agent string
            error_message: Error message if login failed
        """
        from app.models.user import User
        user = User.query.filter_by(email=email).first()

        # For login attempts, we may not have a tenant_id yet
        # Use a sentinel value of 0 for pre-login events
        log = AuditLog(
            event_type='login_attempt',
            event_status='success' if success else 'failure',
            user_id=user.id if user else None,
            tenant_id=0,  # Sentinel value for system-level events
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message
        )

        details = {'email': email}
        if not user:
            details['reason'] = 'User not found'
        log.set_details(details)

        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def get_failed_login_attempts(user_id, minutes=15):
        """
        Get failed login attempts for a user in the last N minutes

        Args:
            user_id: User ID to check
            minutes: Time window to check (default 15 minutes)

        Returns:
            Count of failed login attempts
        """
        from datetime import timedelta
        threshold = datetime.utcnow() - timedelta(minutes=minutes)

        return AuditLog.query.filter(
            AuditLog.user_id == user_id,
            AuditLog.event_type == 'login_attempt',
            AuditLog.event_status == 'failure',
            AuditLog.created_at >= threshold
        ).count()

    @staticmethod
    def should_lock_account(user_id, threshold=5, window_minutes=15):
        """
        Check if account should be locked based on failed login attempts

        Args:
            user_id: User ID to check
            threshold: Number of failed attempts before locking (default 5)
            window_minutes: Time window to check (default 15 minutes)

        Returns:
            True if account should be locked
        """
        failed_attempts = AuditLog.get_failed_login_attempts(user_id, window_minutes)
        return failed_attempts >= threshold
