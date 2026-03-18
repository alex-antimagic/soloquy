from datetime import datetime
from app import db


class StatusPageConfig(db.Model):
    """Status page configuration per tenant (1:1 with Website)"""
    __tablename__ = 'status_page_configs'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'),
                          unique=True, nullable=False, index=True)

    # Configuration
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    page_title = db.Column(db.String(200), default='System Status')
    page_description = db.Column(db.Text, default='Current status of all services')
    support_url = db.Column(db.String(500))  # Link to support/help

    # Display Settings
    show_incident_history_days = db.Column(db.Integer, default=90)  # How far back to show

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    website = db.relationship('Website', back_populates='status_page_config')
    components = db.relationship('StatusComponent', back_populates='config',
                                cascade='all, delete-orphan', order_by='StatusComponent.position')
    incidents = db.relationship('StatusIncident', back_populates='config',
                               cascade='all, delete-orphan')
    subscribers = db.relationship('StatusSubscriber', back_populates='config',
                                 cascade='all, delete-orphan')

    def __repr__(self):
        return f'<StatusPageConfig website_id={self.website_id}>'
