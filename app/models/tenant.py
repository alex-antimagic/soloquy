from datetime import datetime
from app import db


class Tenant(db.Model):
    """Tenant (Business) model for multi-tenancy"""
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)

    # Settings
    logo_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Business Intelligence
    website_url = db.Column(db.String(500))  # Company website
    company_size = db.Column(db.String(50))  # "1-10", "11-50", "51-200", "201-500", "501+"
    business_context = db.Column(db.Text)  # JSON with scraped business intelligence
    custom_context = db.Column(db.Text)  # User-provided context (markdown/text) about business/family
    context_scraped_at = db.Column(db.DateTime)  # When context was last updated
    context_scraping_status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed, skipped
    context_scraping_error = db.Column(db.Text)  # Error message if scraping failed

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    memberships = db.relationship('TenantMembership', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    departments = db.relationship('Department', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    # Note: projects and tasks relationships are defined by backrefs in their respective models
    # but we need to ensure cascade delete by manually deleting them in the delete route

    def __repr__(self):
        return f'<Tenant {self.name}>'

    def get_members(self, role=None):
        """Get all members of this tenant, optionally filtered by role"""
        from app.models.user import User
        query = User.query.join(TenantMembership).filter(
            TenantMembership.tenant_id == self.id,
            TenantMembership.is_active == True
        )
        if role:
            query = query.filter(TenantMembership.role == role)
        return query.all()

    def get_departments(self):
        """Get all departments in this tenant"""
        return self.departments.filter_by(is_active=True).all()

    def add_member(self, user, role='member'):
        """Add a user to this tenant"""
        membership = TenantMembership(
            tenant_id=self.id,
            user_id=user.id,
            role=role
        )
        db.session.add(membership)
        return membership


class TenantMembership(db.Model):
    """Association table for User-Tenant relationship with roles"""
    __tablename__ = 'tenant_memberships'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Role within the tenant
    role = db.Column(db.String(50), nullable=False, default='member')  # owner, admin, member
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', back_populates='memberships')
    user = db.relationship('User', back_populates='tenant_memberships')

    # Unique constraint: one membership per user per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'user_id', name='unique_tenant_user'),
    )

    def __repr__(self):
        return f'<TenantMembership tenant_id={self.tenant_id} user_id={self.user_id} role={self.role}>'

    def is_owner(self):
        """Check if membership has owner role"""
        return self.role == 'owner'

    def is_admin(self):
        """Check if membership has admin or owner role"""
        return self.role in ['owner', 'admin']
