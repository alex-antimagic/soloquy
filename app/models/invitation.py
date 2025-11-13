"""
Invitation Model
Manages email invitations to join workspaces
"""
from datetime import datetime, timedelta
import uuid
from app import db


class Invitation(db.Model):
    """Model for workspace invitations sent via email"""

    __tablename__ = 'invitations'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), default='member', nullable=False)  # 'member', 'admin', 'owner'

    # Unique token for invitation link
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Status tracking
    status = db.Column(db.String(20), default='pending', nullable=False)  # 'pending', 'accepted', 'expired'

    # Expiry
    expires_at = db.Column(db.DateTime, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('invitations', lazy='dynamic'))
    invited_by = db.relationship('User', backref=db.backref('sent_invitations', lazy='dynamic'))

    def __repr__(self):
        return f'<Invitation {self.email} to {self.tenant_id}>'

    @staticmethod
    def generate_token():
        """Generate a secure random token for the invitation"""
        return str(uuid.uuid4())

    @classmethod
    def create_invitation(cls, email, tenant_id, invited_by_user_id, role='member', expires_in_days=7):
        """Create a new invitation with automatic token generation and expiry"""
        invitation = cls(
            email=email.lower(),
            tenant_id=tenant_id,
            invited_by_user_id=invited_by_user_id,
            role=role,
            token=cls.generate_token(),
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )
        return invitation

    def is_expired(self):
        """Check if the invitation has expired"""
        return datetime.utcnow() > self.expires_at

    def is_pending(self):
        """Check if the invitation is still pending"""
        return self.status == 'pending' and not self.is_expired()

    def mark_as_accepted(self):
        """Mark the invitation as accepted"""
        self.status = 'accepted'
        self.accepted_at = datetime.utcnow()

    def mark_as_expired(self):
        """Mark the invitation as expired"""
        self.status = 'expired'

    @classmethod
    def get_pending_for_email(cls, email):
        """Get all pending invitations for an email address"""
        return cls.query.filter_by(
            email=email.lower(),
            status='pending'
        ).filter(
            cls.expires_at > datetime.utcnow()
        ).all()
