from datetime import datetime
from app import db


class DealPipeline(db.Model):
    """Deal Pipeline - like Projects for Tasks"""
    __tablename__ = 'deal_pipelines'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Pipeline Info
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#10B981')  # Hex color
    icon = db.Column(db.String(50))  # Emoji or icon class

    # Settings
    is_default = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='deal_pipelines')
    stages = db.relationship('DealStage', back_populates='pipeline', lazy='dynamic',
                            order_by='DealStage.position', cascade='all, delete-orphan')
    deals = db.relationship('Deal', back_populates='pipeline', lazy='dynamic')

    def __repr__(self):
        return f'<DealPipeline {self.name}>'

    def to_dict(self):
        """Convert pipeline to dictionary"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'is_default': self.is_default,
            'is_archived': self.is_archived,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'stage_count': self.stages.count(),
            'deal_count': self.deals.count()
        }
