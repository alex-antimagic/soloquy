from datetime import datetime
from app import db


class StatusComponent(db.Model):
    """Individual system components to monitor (API, Database, etc.)"""
    __tablename__ = 'status_components'

    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('status_page_configs.id'),
                         nullable=False, index=True)

    # Component Info
    name = db.Column(db.String(200), nullable=False)  # "API Server"
    description = db.Column(db.Text)
    position = db.Column(db.Integer, default=0)  # Display order

    # Current Status
    # Options: 'operational', 'degraded_performance', 'partial_outage', 'major_outage'
    status = db.Column(db.String(50), default='operational', nullable=False)

    # Visibility
    is_visible = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status_changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    config = db.relationship('StatusPageConfig', back_populates='components')

    def __repr__(self):
        return f'<StatusComponent {self.name} - {self.status}>'

    def update_status(self, new_status):
        """Update status and track timestamp"""
        if self.status != new_status:
            self.status = new_status
            self.status_changed_at = datetime.utcnow()
