"""
TicketStatusHistory model for tracking ticket status changes
"""
from app import db
from datetime import datetime


class TicketStatusHistory(db.Model):
    __tablename__ = 'ticket_status_history'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # User who made the change

    # Status Change
    from_status = db.Column(db.String(50))  # Previous status (null if first status)
    to_status = db.Column(db.String(50), nullable=False)  # New status

    # Optional Context
    reason = db.Column(db.Text)  # Why the status changed (optional)

    # Timestamp
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    ticket = db.relationship('Ticket', back_populates='status_history')
    changed_by = db.relationship('User', backref=db.backref('ticket_status_changes', lazy='dynamic'))

    def __repr__(self):
        return f'<TicketStatusHistory {self.ticket_id}: {self.from_status} → {self.to_status}>'

    @property
    def changed_by_display_name(self):
        """Get name of user who changed status"""
        if self.changed_by:
            return self.changed_by.full_name
        return 'System'

    @property
    def status_change_display(self):
        """Human-readable status change"""
        if self.from_status:
            return f"{self.from_status.replace('_', ' ').title()} → {self.to_status.replace('_', ' ').title()}"
        return f"Set to {self.to_status.replace('_', ' ').title()}"
