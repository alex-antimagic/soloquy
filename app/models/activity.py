from datetime import datetime
from app import db


class Activity(db.Model):
    """Activity model - track all interactions (calls, emails, meetings, notes)"""
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Activity Type & Content
    activity_type = db.Column(db.String(50), nullable=False)  # call, email, meeting, note, task
    subject = db.Column(db.String(255))
    description = db.Column(db.Text)

    # Relationships - Activity can be linked to multiple entities
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('deals.id'), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), index=True)

    # Scheduling (for future activities)
    scheduled_at = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)

    # Metadata
    priority = db.Column(db.String(20), default='medium')
    outcome = db.Column(db.String(100))  # For completed activities: successful, unsuccessful, rescheduled, etc.

    # Ownership
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='activities')
    company = db.relationship('Company', back_populates='activities')
    contact = db.relationship('Contact', back_populates='activities')
    deal = db.relationship('Deal', back_populates='activities')
    lead = db.relationship('Lead', backref='activities')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_activities')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_activities')

    def __repr__(self):
        return f'<Activity {self.activity_type}: {self.subject}>'

    def get_type_icon(self):
        """Get Bootstrap icon for activity type"""
        type_icons = {
            'call': 'bi-telephone',
            'email': 'bi-envelope',
            'meeting': 'bi-calendar-event',
            'note': 'bi-sticky',
            'task': 'bi-check2-square'
        }
        return type_icons.get(self.activity_type, 'bi-circle')

    def to_dict(self):
        """Convert activity to dictionary"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'activity_type': self.activity_type,
            'subject': self.subject,
            'description': self.description,
            'company_id': self.company_id,
            'contact_id': self.contact_id,
            'deal_id': self.deal_id,
            'lead_id': self.lead_id,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'duration_minutes': self.duration_minutes,
            'completed': self.completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'priority': self.priority,
            'outcome': self.outcome,
            'created_by_id': self.created_by_id,
            'assigned_to_id': self.assigned_to_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'company_name': self.company.name if self.company else None,
            'contact_name': f'{self.contact.first_name} {self.contact.last_name}' if self.contact else None,
            'deal_name': self.deal.name if self.deal else None,
            'created_by_name': self.created_by.full_name if self.created_by else None
        }
