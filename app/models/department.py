from datetime import datetime
from app import db
from app.models.message import Message


class Department(db.Model):
    """Department model for organizing teams within a tenant"""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # Display settings
    color = db.Column(db.String(7), default='#6C757D')  # Hex color code
    icon = db.Column(db.String(50))  # Icon class or emoji

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', back_populates='departments')
    agents = db.relationship('Agent', back_populates='department', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='department', lazy='dynamic')

    # Unique constraint: one slug per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'slug', name='unique_department_slug_per_tenant'),
    )

    def __repr__(self):
        return f'<Department {self.name}>'

    def get_agents(self):
        """Get all active agents in this department"""
        return self.agents.filter_by(is_active=True).all()

    def get_primary_agent(self):
        """Get the primary (default) agent for this department"""
        return self.agents.filter_by(is_active=True, is_primary=True).first()

    def get_recent_messages(self, limit=50):
        """Get recent messages in this department"""
        return self.messages.order_by(Message.created_at.desc()).limit(limit).all()

    def get_message_count(self):
        """Get total number of messages in this department"""
        return self.messages.count()

    def get_active_members(self):
        """Get list of users who have sent messages in this department"""
        from app.models.user import User
        # Get unique sender IDs from messages
        sender_ids = db.session.query(Message.sender_id).filter(
            Message.department_id == self.id,
            Message.sender_id.isnot(None)
        ).distinct().all()

        if not sender_ids:
            return []

        # Fetch users
        user_ids = [sid[0] for sid in sender_ids]
        return User.query.filter(User.id.in_(user_ids)).all()

    def get_ai_interaction_count(self, days=7):
        """Get number of AI agent messages in the last N days"""
        from datetime import datetime, timedelta
        since = datetime.utcnow() - timedelta(days=days)

        return self.messages.filter(
            Message.agent_id.isnot(None),
            Message.created_at >= since
        ).count()

    def get_weekly_activity(self):
        """Get message count for the last 7 days"""
        from datetime import datetime, timedelta
        since = datetime.utcnow() - timedelta(days=7)

        return self.messages.filter(Message.created_at >= since).count()
