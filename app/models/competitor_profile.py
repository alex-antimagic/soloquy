"""
Competitor Profile model for tracking competitors in website competitive analysis
"""
from datetime import datetime
from app import db


class CompetitorProfile(db.Model):
    """Stores competitor information per website"""
    __tablename__ = 'competitor_profiles'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'), nullable=False, index=True)

    # Competitor info
    company_name = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    logo_url = db.Column(db.String(500))
    industry = db.Column(db.String(100))

    # Discovery metadata
    is_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    suggested_by_agent = db.Column(db.Boolean, default=False)
    confidence_score = db.Column(db.Float)  # 0.0-1.0
    source = db.Column(db.String(50))  # 'manual', 'ai_suggested', 'enrichment_cache'

    # Optional notes
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    website = db.relationship('Website', backref=db.backref('competitors', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def __repr__(self):
        return f'<CompetitorProfile {self.company_name} ({self.domain})>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'website_id': self.website_id,
            'company_name': self.company_name,
            'domain': self.domain,
            'logo_url': self.logo_url,
            'industry': self.industry,
            'is_confirmed': self.is_confirmed,
            'suggested_by_agent': self.suggested_by_agent,
            'confidence_score': self.confidence_score,
            'source': self.source,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
