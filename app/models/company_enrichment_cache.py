from datetime import datetime, timedelta
from app import db


class CompanyEnrichmentCache(db.Model):
    """Global cache for company enrichment data - shared across all tenants"""
    __tablename__ = 'company_enrichment_cache'

    id = db.Column(db.Integer, primary_key=True)

    # Domain is the unique key (e.g., "acme.com")
    domain = db.Column(db.String(500), nullable=False, unique=True, index=True)

    # Scraping metadata
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    raw_html = db.Column(db.Text)  # Cached website HTML

    # Enrichment data (stored as JSON strings)
    company_basics = db.Column(db.Text)  # JSON: industry, size, description, founding_year, employee_count
    products_services = db.Column(db.Text)  # JSON: what they sell, product categories
    competitors = db.Column(db.Text)  # JSON: competitor list, market positioning
    key_people = db.Column(db.Text)  # JSON: executives, decision makers, contact info

    # Social/Professional URLs
    linkedin_company_url = db.Column(db.String(500))
    twitter_handle = db.Column(db.String(100))

    # Cache management
    ttl_expires_at = db.Column(db.DateTime, nullable=False, index=True)  # 30 days default

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    companies = db.relationship('Company', back_populates='enrichment_cache', lazy='dynamic')

    def __repr__(self):
        return f'<CompanyEnrichmentCache {self.domain}>'

    @staticmethod
    def get_default_ttl():
        """Default cache TTL is 30 days"""
        return datetime.utcnow() + timedelta(days=30)

    def is_expired(self):
        """Check if cache entry has expired"""
        return datetime.utcnow() > self.ttl_expires_at

    def refresh_ttl(self):
        """Extend TTL by another 30 days"""
        self.ttl_expires_at = self.get_default_ttl()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        """Convert cache entry to dictionary"""
        import json
        return {
            'id': self.id,
            'domain': self.domain,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None,
            'company_basics': json.loads(self.company_basics) if self.company_basics else None,
            'products_services': json.loads(self.products_services) if self.products_services else None,
            'competitors': json.loads(self.competitors) if self.competitors else None,
            'key_people': json.loads(self.key_people) if self.key_people else None,
            'linkedin_company_url': self.linkedin_company_url,
            'twitter_handle': self.twitter_handle,
            'ttl_expires_at': self.ttl_expires_at.isoformat() if self.ttl_expires_at else None,
            'is_expired': self.is_expired()
        }
