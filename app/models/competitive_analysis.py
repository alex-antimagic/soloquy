"""
Competitive Analysis model for storing results of competitor website analysis
"""
from datetime import datetime
from app import db


class CompetitiveAnalysis(db.Model):
    """Stores results of competitive analysis runs"""
    __tablename__ = 'competitive_analyses'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'), nullable=False, index=True)

    # Analysis metadata
    analysis_type = db.Column(db.String(50), default='comprehensive')  # 'comprehensive', 'website', 'marketing'
    status = db.Column(db.String(50), default='pending')  # 'pending', 'processing', 'completed', 'failed'

    # Competitors analyzed (snapshot at analysis time)
    competitor_ids = db.Column(db.JSON)  # [1, 2, 3] - CompetitorProfile IDs
    competitor_count = db.Column(db.Integer, default=0)

    # Analysis results (JSON structures)
    executive_summary = db.Column(db.Text)  # 2-3 sentence summary
    strengths = db.Column(db.JSON)  # [{title, description, score}]
    gaps = db.Column(db.JSON)  # [{title, description, benchmark, priority, cta_text, cta_route}]
    opportunities = db.Column(db.JSON)  # [{title, priority, impact, actions, description}]
    comparison_matrix = db.Column(db.JSON)  # {metrics: [{name, your_value, comp1_value, ...}]}
    detailed_findings = db.Column(db.JSON)  # Full per-competitor analysis

    # Agent tracking
    analyzed_by_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    website = db.relationship('Website', backref=db.backref('competitive_analyses', lazy='dynamic'))
    analyzed_by_agent = db.relationship('Agent', foreign_keys=[analyzed_by_agent_id])

    def __repr__(self):
        return f'<CompetitiveAnalysis {self.id} (Website: {self.website_id}, Status: {self.status})>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'website_id': self.website_id,
            'analysis_type': self.analysis_type,
            'status': self.status,
            'competitor_ids': self.competitor_ids,
            'competitor_count': self.competitor_count,
            'executive_summary': self.executive_summary,
            'strengths': self.strengths,
            'gaps': self.gaps,
            'opportunities': self.opportunities,
            'comparison_matrix': self.comparison_matrix,
            'detailed_findings': self.detailed_findings,
            'analyzed_by_agent_id': self.analyzed_by_agent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def get_opportunity_count(self):
        """Get count of opportunities from analysis"""
        return len(self.opportunities) if self.opportunities else 0

    def is_complete(self):
        """Check if analysis is complete"""
        return self.status == 'completed'

    def is_in_progress(self):
        """Check if analysis is currently running"""
        return self.status in ['pending', 'processing']
