from datetime import datetime
from app import db


class StatusIncident(db.Model):
    """Incidents affecting service availability"""
    __tablename__ = 'status_incidents'

    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('status_page_configs.id'),
                         nullable=False, index=True)

    # Incident Info
    title = db.Column(db.String(255), nullable=False)  # "Database Connection Issues"

    # Status: 'investigating', 'identified', 'monitoring', 'resolved'
    status = db.Column(db.String(50), default='investigating', nullable=False)

    # Severity: 'minor', 'major', 'critical'
    severity = db.Column(db.String(50), default='minor', nullable=False)

    # Impact: Which components are affected (JSON array of component IDs)
    affected_component_ids = db.Column(db.JSON, default=list)

    # Visibility
    is_published = db.Column(db.Boolean, default=False)  # Draft vs published

    # Authorship
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Notification Tracking
    notification_sent = db.Column(db.Boolean, default=False)
    notification_sent_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    # Relationships
    config = db.relationship('StatusPageConfig', back_populates='incidents')
    created_by = db.relationship('User')
    updates = db.relationship('IncidentUpdate', back_populates='incident',
                             cascade='all, delete-orphan',
                             order_by='IncidentUpdate.created_at.desc()')

    __table_args__ = (
        db.Index('idx_config_status', 'config_id', 'status'),
        db.Index('idx_config_created', 'config_id', 'created_at'),
    )

    def __repr__(self):
        return f'<StatusIncident {self.title} - {self.status}>'

    def get_latest_update(self):
        """Get most recent update"""
        return self.updates[0] if self.updates else None

    def get_affected_components(self):
        """Get list of affected StatusComponent objects"""
        from app.models.status_component import StatusComponent

        if not self.affected_component_ids:
            return []
        return StatusComponent.query.filter(
            StatusComponent.id.in_(self.affected_component_ids)
        ).all()
