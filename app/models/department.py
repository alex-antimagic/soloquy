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

    # Access Control
    access_control = db.Column(db.String(20), default='all', nullable=False)
    # Values: 'all' (all workspace members), 'members' (explicit membership required)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', back_populates='departments')
    agents = db.relationship('Agent', back_populates='department', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='department', lazy='dynamic')
    memberships = db.relationship('DepartmentMembership', back_populates='department',
                                   cascade='all, delete-orphan', lazy='dynamic')

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

    def can_user_access(self, user):
        """
        Check if a user has access to this department

        Args:
            user: User object

        Returns:
            Boolean indicating if user can access this department
        """
        # Check workspace access first
        if not user.has_tenant_access(self.tenant_id):
            return False

        # Workspace owners and admins always have access (bypass restrictions)
        user_role = user.get_role_in_tenant(self.tenant_id)
        if user_role in ['owner', 'admin']:
            return True

        # If department is open to all workspace members
        if self.access_control == 'all':
            return True

        # Check explicit membership
        from app.models.department_membership import DepartmentMembership
        membership = DepartmentMembership.query.filter_by(
            department_id=self.id,
            user_id=user.id,
            is_active=True
        ).first()

        return membership is not None

    def get_members(self):
        """
        Get all users who have access to this department

        Returns:
            List of User objects
        """
        from app.models.user import User

        # If department is open to all, return all workspace members
        if self.access_control == 'all':
            return self.tenant.get_members()

        # Return only explicit members
        from app.models.department_membership import DepartmentMembership
        member_users = User.query.join(DepartmentMembership).filter(
            DepartmentMembership.department_id == self.id,
            DepartmentMembership.is_active == True
        ).all()

        # Also include workspace owners and admins (they always have access)
        admin_users = [u for u in self.tenant.get_members()
                       if u.get_role_in_tenant(self.tenant_id) in ['owner', 'admin']]

        # Combine and deduplicate
        all_members = list(set(member_users + admin_users))
        return all_members

    def add_member(self, user):
        """
        Add a user to this department

        Args:
            user: User object to add

        Returns:
            DepartmentMembership object
        """
        from app.models.department_membership import DepartmentMembership

        # Check if membership already exists
        existing = DepartmentMembership.query.filter_by(
            department_id=self.id,
            user_id=user.id
        ).first()

        if existing:
            # Reactivate if inactive
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            return existing

        # Create new membership
        membership = DepartmentMembership(
            department_id=self.id,
            user_id=user.id,
            is_active=True
        )
        db.session.add(membership)
        return membership

    def remove_member(self, user):
        """
        Remove a user from this department

        Args:
            user: User object to remove

        Returns:
            Boolean indicating if member was removed
        """
        from app.models.department_membership import DepartmentMembership

        membership = DepartmentMembership.query.filter_by(
            department_id=self.id,
            user_id=user.id
        ).first()

        if membership:
            membership.is_active = False
            membership.updated_at = datetime.utcnow()
            return True

        return False

    def get_member_count(self):
        """Get count of users with access to this department"""
        return len(self.get_members())
