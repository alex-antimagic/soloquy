"""
Candidate Model
Tracks job candidates in the recruitment pipeline
"""
from datetime import datetime
import json
from app import db


class Candidate(db.Model):
    """Candidate model for recruitment pipeline"""
    __tablename__ = 'candidates'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    job_posting_id = db.Column(db.Integer, db.ForeignKey('job_postings.id', ondelete='SET NULL'), nullable=True, index=True)

    # Contact information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))

    # Job application details
    position = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='applied', index=True)  # applied, screening, interviewing, offer_extended, hired, rejected
    applied_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    # Application materials
    resume_url = db.Column(db.String(500))
    cover_letter = db.Column(db.Text)
    linkedin_url = db.Column(db.String(500))

    # Skills and experience
    skills = db.Column(db.Text)  # JSON array
    experience_years = db.Column(db.Integer)
    source = db.Column(db.String(100))  # e.g., 'LinkedIn', 'Referral', 'Job Board'

    # Scoring
    overall_score = db.Column(db.Float)  # 0-100
    category_scores = db.Column(db.Text)  # JSON dict: {'technical': 85, 'communication': 90}
    notes = db.Column(db.Text)  # JSON array of assessment notes

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('candidates', lazy='dynamic'))
    job_posting = db.relationship('JobPosting', backref=db.backref('candidates', lazy='dynamic'))
    interviews = db.relationship('Interview', back_populates='candidate', lazy='dynamic',
                                 cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Candidate {self.full_name} - {self.position}>'

    @property
    def full_name(self):
        """Get candidate's full name"""
        return f'{self.first_name} {self.last_name}'

    @property
    def skills_list(self):
        """Get skills as Python list"""
        if not self.skills:
            return []
        try:
            return json.loads(self.skills)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_interview_history(self):
        """Get all interviews for this candidate, ordered by date"""
        return self.interviews.order_by(Interview.scheduled_date.desc()).all()

    def update_category_scores(self, scores_dict):
        """
        Update category scores

        Args:
            scores_dict: Dictionary of category scores, e.g., {'technical': 85, 'communication': 90}
        """
        if not self.category_scores:
            current_scores = {}
        else:
            try:
                current_scores = json.loads(self.category_scores)
            except (json.JSONDecodeError, TypeError):
                current_scores = {}

        # Update with new scores
        current_scores.update(scores_dict)
        self.category_scores = json.dumps(current_scores)

    def add_assessment_note(self, note, score=None, assessed_by=None):
        """
        Add an assessment note

        Args:
            note: Assessment note text
            score: Optional score (0-100)
            assessed_by: Name/email of assessor
        """
        if not self.notes:
            notes_list = []
        else:
            try:
                notes_list = json.loads(self.notes)
            except (json.JSONDecodeError, TypeError):
                notes_list = []

        note_entry = {
            'note': note,
            'date': datetime.utcnow().isoformat(),
            'assessed_by': assessed_by
        }

        if score is not None:
            note_entry['score'] = score

        notes_list.append(note_entry)
        self.notes = json.dumps(notes_list)

    def update_status(self, new_status, reason=None, updated_by=None):
        """
        Update candidate status with audit trail

        Args:
            new_status: New status value
            reason: Optional reason for status change
            updated_by: Name/email of person making the change
        """
        old_status = self.status
        self.status = new_status

        # Add status change to notes
        status_note = f'Status changed from {old_status} to {new_status}'
        if reason:
            status_note += f': {reason}'

        self.add_assessment_note(status_note, assessed_by=updated_by)
