"""
Similar Lead Discovery Model
Tracks jobs to discover leads similar to existing customers
"""
from datetime import datetime
from app import db


class SimilarLeadDiscovery(db.Model):
    """Tracks similar lead discovery jobs, their progress, and results"""
    __tablename__ = 'similar_lead_discoveries'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Source company (reference customer)
    reference_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    reference_company_name = db.Column(db.String(255))  # Cached for display

    # Discovery configuration
    similarity_criteria = db.Column(db.Text)  # JSON: {industry, business_model, tech_stack, company_size}
    search_strategy = db.Column(db.Text)  # JSON: {cache, ai, google_search}
    max_results = db.Column(db.Integer, default=20)

    # Job status
    status = db.Column(db.String(20), default='pending', index=True)  # pending, processing, completed, failed
    progress_percentage = db.Column(db.Integer, default=0)
    progress_message = db.Column(db.String(500))

    # Results
    discovered_count = db.Column(db.Integer, default=0)  # Total companies found
    leads_created = db.Column(db.Integer, default=0)  # Leads auto-created
    discovery_summary = db.Column(db.Text)  # AI-generated summary
    error_message = db.Column(db.Text)

    # Discovery metadata
    discovered_companies = db.Column(db.Text)  # JSON: [{name, domain, similarity_score, source}]

    # Initiation tracking
    initiated_by = db.Column(db.String(20))  # 'agent', 'ui', 'api'
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    initiated_by_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref='similar_lead_discoveries')
    reference_company = db.relationship('Company', foreign_keys=[reference_company_id])
    initiated_by_user = db.relationship('User', foreign_keys=[initiated_by_user_id])
    initiated_by_agent = db.relationship('Agent', foreign_keys=[initiated_by_agent_id])

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'reference_company_id': self.reference_company_id,
            'reference_company_name': self.reference_company_name,
            'similarity_criteria': self.similarity_criteria,
            'max_results': self.max_results,
            'status': self.status,
            'progress_percentage': self.progress_percentage,
            'progress_message': self.progress_message,
            'discovered_count': self.discovered_count,
            'leads_created': self.leads_created,
            'discovery_summary': self.discovery_summary,
            'error_message': self.error_message,
            'initiated_by': self.initiated_by,
            'initiated_by_user_id': self.initiated_by_user_id,
            'initiated_by_agent_id': self.initiated_by_agent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
