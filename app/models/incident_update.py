from datetime import datetime
from app import db


class IncidentUpdate(db.Model):
    """Timeline updates for incidents"""
    __tablename__ = 'incident_updates'

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('status_incidents.id'),
                           nullable=False, index=True)

    # Update Content
    message = db.Column(db.Text, nullable=False)

    # Update Type: 'investigating', 'identified', 'monitoring', 'resolved', 'update'
    update_type = db.Column(db.String(50), default='update', nullable=False)

    # Authorship
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Notification
    notify_subscribers = db.Column(db.Boolean, default=False)
    notification_sent = db.Column(db.Boolean, default=False)
    notification_sent_at = db.Column(db.DateTime)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    incident = db.relationship('StatusIncident', back_populates='updates')
    created_by = db.relationship('User')

    def __repr__(self):
        return f'<IncidentUpdate {self.update_type} - {self.created_at}>'
