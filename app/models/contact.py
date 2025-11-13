from datetime import datetime
from app import db


class Contact(db.Model):
    """Contact model - individual people at companies"""
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), index=True)  # Optional

    # Personal Information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(50))
    mobile = db.Column(db.String(50))

    # Professional Information
    job_title = db.Column(db.String(200))
    department = db.Column(db.String(100))
    seniority_level = db.Column(db.String(50))  # IC, Manager, Director, VP, C-Level

    # Social
    linkedin_url = db.Column(db.String(500))
    twitter_handle = db.Column(db.String(100))
    avatar_url = db.Column(db.String(500))

    # Contact Preferences
    preferred_contact_method = db.Column(db.String(20))  # email, phone, linkedin
    timezone = db.Column(db.String(50))

    # Metadata
    description = db.Column(db.Text)
    tags = db.Column(db.String(500))

    # Status & Lead Info
    status = db.Column(db.String(20), default='active')  # active, inactive, bounced, unsubscribed
    lead_source = db.Column(db.String(100))  # website, referral, event, cold_outreach, etc.
    lead_score = db.Column(db.Integer, default=0)  # 0-100 scoring
    lifecycle_stage = db.Column(db.String(50), default='subscriber')  # subscriber, lead, mql, sql, opportunity, customer

    # Ownership
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref='contacts')
    company = db.relationship('Company', back_populates='contacts')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_contacts')
    activities = db.relationship('Activity', back_populates='contact', lazy='dynamic')

    def __repr__(self):
        return f'<Contact {self.first_name} {self.last_name}>'

    @property
    def full_name(self):
        """Get full name of contact"""
        return f'{self.first_name} {self.last_name}'

    def to_dict(self):
        """Convert contact to dictionary"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'company_id': self.company_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'job_title': self.job_title,
            'department': self.department,
            'seniority_level': self.seniority_level,
            'linkedin_url': self.linkedin_url,
            'twitter_handle': self.twitter_handle,
            'avatar_url': self.avatar_url,
            'preferred_contact_method': self.preferred_contact_method,
            'timezone': self.timezone,
            'description': self.description,
            'tags': self.tags,
            'status': self.status,
            'lead_source': self.lead_source,
            'lead_score': self.lead_score,
            'lifecycle_stage': self.lifecycle_stage,
            'owner_id': self.owner_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_contacted_at': self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            'company_name': self.company.name if self.company else None
        }
