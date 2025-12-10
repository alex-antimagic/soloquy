"""
Job Posting Model
Tracks job postings and openings
"""
from datetime import datetime
from app import db


class JobPosting(db.Model):
    """Job posting model for recruitment"""
    __tablename__ = 'job_postings'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Job details
    title = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100))
    location = db.Column(db.String(200))
    employment_type = db.Column(db.String(50))  # full-time, part-time, contract, internship

    # Job description
    description = db.Column(db.Text)  # Rich text HTML
    requirements = db.Column(db.Text)  # Rich text HTML

    # Compensation
    salary_range_min = db.Column(db.Numeric(12, 2))
    salary_range_max = db.Column(db.Numeric(12, 2))
    salary_currency = db.Column(db.String(3), default='USD')

    # Status
    status = db.Column(db.String(50), nullable=False, default='draft', index=True)  # draft, published, closed
    published_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    # Metrics (denormalized for performance)
    application_count = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('job_postings', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('job_postings', lazy='dynamic'))
    # candidates relationship is defined in Candidate model

    def __repr__(self):
        return f'<JobPosting {self.title} - {self.status}>'

    def publish(self):
        """Publish the job posting"""
        if self.status == 'draft':
            self.status = 'published'
            self.published_at = datetime.utcnow()

    def close(self):
        """Close the job posting"""
        if self.status == 'published':
            self.status = 'closed'
            self.closed_at = datetime.utcnow()

    def reopen(self):
        """Reopen a closed job posting"""
        if self.status == 'closed':
            self.status = 'published'
            self.closed_at = None

    def increment_application_count(self):
        """Increment the application count"""
        self.application_count += 1
