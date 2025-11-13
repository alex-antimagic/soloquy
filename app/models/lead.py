from datetime import datetime
from app import db


class Lead(db.Model):
    """Lead model - potential customers before qualification"""
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Basic Information
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(50))

    # Company Information
    company_name = db.Column(db.String(255))
    company_website = db.Column(db.String(500))
    job_title = db.Column(db.String(200))

    # Lead Details
    lead_source = db.Column(db.String(100))  # website, referral, cold_call, event, advertising
    lead_score = db.Column(db.Integer, default=0)  # 0-100
    status = db.Column(db.String(50), default='new')  # new, contacted, qualified, unqualified, converted

    # Qualification (BANT)
    budget = db.Column(db.String(50))  # Estimated budget range
    timeline = db.Column(db.String(50))  # When they plan to buy
    authority = db.Column(db.String(50))  # Decision maker status
    need = db.Column(db.Text)  # What problem they're trying to solve

    # Enrichment
    description = db.Column(db.Text)
    notes = db.Column(db.Text)
    tags = db.Column(db.String(500))

    # Conversion
    converted = db.Column(db.Boolean, default=False)
    converted_contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    converted_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    converted_deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'))
    converted_at = db.Column(db.DateTime)

    # Ownership
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))  # AI agent can handle lead

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref='leads')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_leads')
    assigned_agent = db.relationship('Agent', foreign_keys=[assigned_to_agent_id], backref='assigned_leads')

    def __repr__(self):
        return f'<Lead {self.first_name} {self.last_name}>'

    @property
    def full_name(self):
        """Get full name of lead"""
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return 'Unknown'

    def to_dict(self):
        """Convert lead to dictionary"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'company_name': self.company_name,
            'company_website': self.company_website,
            'job_title': self.job_title,
            'lead_source': self.lead_source,
            'lead_score': self.lead_score,
            'status': self.status,
            'budget': self.budget,
            'timeline': self.timeline,
            'authority': self.authority,
            'need': self.need,
            'description': self.description,
            'notes': self.notes,
            'tags': self.tags,
            'converted': self.converted,
            'converted_contact_id': self.converted_contact_id,
            'converted_company_id': self.converted_company_id,
            'converted_deal_id': self.converted_deal_id,
            'converted_at': self.converted_at.isoformat() if self.converted_at else None,
            'owner_id': self.owner_id,
            'assigned_to_agent_id': self.assigned_to_agent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_contacted_at': self.last_contacted_at.isoformat() if self.last_contacted_at else None
        }
