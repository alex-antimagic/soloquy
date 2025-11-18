from datetime import datetime
from flask_login import UserMixin
from app import db, bcrypt, login_manager


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """User model for authentication and profile"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Profile information
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    avatar_url = db.Column(db.String(255))
    title = db.Column(db.String(100))  # Job title (CEO, CTO, Support Manager, etc.)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False)  # Global admin access
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    # Plan & Billing
    plan = db.Column(db.String(20), default='free', nullable=False)  # 'free' or 'pro'
    stripe_customer_id = db.Column(db.String(255))  # For Stripe integration
    stripe_subscription_id = db.Column(db.String(255))  # For Stripe subscriptions

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant_memberships = db.relationship('TenantMembership', back_populates='user', lazy='dynamic')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', back_populates='sender', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        """Hash and set the user's password"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Check if provided password matches the hash"""
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        if self.first_name:
            return self.first_name
        return self.email.split('@')[0]  # Use email prefix as display name

    def is_online_now(self):
        """Check if user is currently online (real-time via Socket.IO)"""
        try:
            from app.services.socketio_manager import socketio_manager
            return socketio_manager.is_user_online(self.id)
        except:
            return False  # Fallback to offline if Socket.IO manager unavailable

    def get_tenants(self):
        """Get all tenants this user belongs to"""
        from app.models.tenant import Tenant, TenantMembership
        return Tenant.query.join(TenantMembership).filter(
            TenantMembership.user_id == self.id,
            TenantMembership.is_active == True
        ).all()

    def has_tenant_access(self, tenant_id):
        """Check if user has access to a specific tenant"""
        from app.models.tenant import TenantMembership
        membership = TenantMembership.query.filter_by(
            user_id=self.id,
            tenant_id=tenant_id,
            is_active=True
        ).first()
        return membership is not None

    def get_role_in_tenant(self, tenant_id):
        """Get user's role in a specific tenant"""
        from app.models.tenant import TenantMembership
        membership = TenantMembership.query.filter_by(
            user_id=self.id,
            tenant_id=tenant_id,
            is_active=True
        ).first()
        return membership.role if membership else None

    def get_workspace_limit(self):
        """Get the maximum number of workspaces allowed for this user's plan"""
        if self.plan == 'pro':
            return None  # Unlimited
        return 1  # Free plan: 1 workspace

    def get_workspace_count(self):
        """Get the number of workspaces owned by this user"""
        from app.models.tenant import TenantMembership
        return TenantMembership.query.filter_by(
            user_id=self.id,
            role='owner',
            is_active=True
        ).count()

    def can_create_workspace(self):
        """Check if user can create another workspace based on their plan"""
        limit = self.get_workspace_limit()
        if limit is None:  # Unlimited (pro plan)
            return True
        return self.get_workspace_count() < limit

    def is_pro(self):
        """Check if user has pro plan"""
        return self.plan == 'pro'
