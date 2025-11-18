from datetime import datetime
from app import db


class Company(db.Model):
    """Company/Account model - organizations you do business with"""
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Basic Information
    name = db.Column(db.String(255), nullable=False, index=True)
    website = db.Column(db.String(500))
    industry = db.Column(db.String(100))
    company_size = db.Column(db.String(50))  # "1-10", "11-50", "51-200", "201-500", "501+"
    annual_revenue = db.Column(db.String(50))  # "$0-1M", "$1M-10M", "$10M-50M", "$50M+"

    # Address Information
    address_street = db.Column(db.String(255))
    address_city = db.Column(db.String(100))
    address_state = db.Column(db.String(100))
    address_postal_code = db.Column(db.String(20))
    address_country = db.Column(db.String(100))

    # Social/Contact
    phone = db.Column(db.String(50))
    linkedin_url = db.Column(db.String(500))
    twitter_handle = db.Column(db.String(100))

    # Business Intelligence
    description = db.Column(db.Text)
    business_context = db.Column(db.Text)  # JSON with scraped/enriched data
    tags = db.Column(db.String(500))  # Comma-separated tags

    # Lead Enrichment (AI-generated)
    enrichment_status = db.Column(db.String(20), index=True)  # 'pending', 'processing', 'completed', 'failed'
    enriched_at = db.Column(db.DateTime)
    enrichment_error = db.Column(db.Text)
    lead_score = db.Column(db.Integer, index=True)  # 0-100 AI-calculated fit score
    buying_signals = db.Column(db.Text)  # JSON: detected signals (hiring, funding, expansion)
    competitive_position = db.Column(db.Text)  # Market position analysis
    enrichment_summary = db.Column(db.Text)  # AI-generated summary
    enrichment_cache_id = db.Column(db.Integer, db.ForeignKey('company_enrichment_cache.id'))

    # Status & Classification
    status = db.Column(db.String(20), default='active')  # active, inactive, prospect, customer
    lifecycle_stage = db.Column(db.String(50), default='lead')  # lead, qualified, customer, churned

    # Ownership
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref='companies')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_companies')
    enrichment_cache = db.relationship('CompanyEnrichmentCache', back_populates='companies', foreign_keys=[enrichment_cache_id])
    contacts = db.relationship('Contact', back_populates='company', lazy='dynamic')
    deals = db.relationship('Deal', back_populates='company', lazy='dynamic')
    activities = db.relationship('Activity', back_populates='company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.name}>'

    def to_dict(self):
        """Convert company to dictionary"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'website': self.website,
            'industry': self.industry,
            'company_size': self.company_size,
            'annual_revenue': self.annual_revenue,
            'address_street': self.address_street,
            'address_city': self.address_city,
            'address_state': self.address_state,
            'address_postal_code': self.address_postal_code,
            'address_country': self.address_country,
            'phone': self.phone,
            'linkedin_url': self.linkedin_url,
            'twitter_handle': self.twitter_handle,
            'description': self.description,
            'tags': self.tags,
            'status': self.status,
            'lifecycle_stage': self.lifecycle_stage,
            'owner_id': self.owner_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_contacted_at': self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            'contact_count': self.contacts.count(),
            'deal_count': self.deals.count()
        }
