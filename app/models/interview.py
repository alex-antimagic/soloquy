"""
Interview Model
Tracks scheduled interviews for candidates
"""
from datetime import datetime
import json
from app import db


class Interview(db.Model):
    """Interview model for recruitment pipeline"""
    __tablename__ = 'interviews'

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Interview details
    interview_type = db.Column(db.String(50), nullable=False)  # phone_screen, technical, behavioral, panel, final
    scheduled_date = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    location = db.Column(db.String(500))  # Physical location or video meeting link

    # Interviewers
    interviewers = db.Column(db.Text)  # JSON array of email addresses

    # Interview feedback
    notes = db.Column(db.Text)
    feedback = db.Column(db.Text)
    score = db.Column(db.Float)  # 0-100

    # Status
    status = db.Column(db.String(50), nullable=False, default='scheduled')  # scheduled, completed, cancelled

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    candidate = db.relationship('Candidate', back_populates='interviews')
    tenant = db.relationship('Tenant', backref=db.backref('interviews', lazy='dynamic'))

    def __repr__(self):
        return f'<Interview {self.interview_type} for Candidate {self.candidate_id}>'

    @property
    def interviewers_list(self):
        """Get interviewers as Python list"""
        if not self.interviewers:
            return []
        try:
            return json.loads(self.interviewers)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_interviewers(self, interviewer_emails):
        """
        Set interviewers from a list

        Args:
            interviewer_emails: List of email addresses
        """
        if isinstance(interviewer_emails, list):
            self.interviewers = json.dumps(interviewer_emails)
        else:
            self.interviewers = json.dumps([interviewer_emails])

    def mark_completed(self, feedback_text=None, score=None):
        """
        Mark interview as completed

        Args:
            feedback_text: Optional feedback text
            score: Optional score (0-100)
        """
        self.status = 'completed'
        if feedback_text:
            self.feedback = feedback_text
        if score is not None:
            self.score = score

    def cancel(self):
        """Cancel the interview"""
        self.status = 'cancelled'
