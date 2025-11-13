from datetime import datetime
from app import db


class DealStage(db.Model):
    """Deal Stage - like StatusColumn for Tasks"""
    __tablename__ = 'deal_stages'

    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('deal_pipelines.id'), nullable=False)

    # Stage Info
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(7))  # Hex color

    # Stage Configuration
    probability = db.Column(db.Integer, default=0)  # Default probability for deals in this stage
    is_closed_won = db.Column(db.Boolean, default=False)  # Marks deal as won
    is_closed_lost = db.Column(db.Boolean, default=False)  # Marks deal as lost

    # Automation
    expected_duration_days = db.Column(db.Integer)  # How long deals typically stay here

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pipeline = db.relationship('DealPipeline', back_populates='stages')
    deals = db.relationship('Deal', back_populates='stage', lazy='dynamic')

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('pipeline_id', 'position', name='unique_stage_position'),
    )

    def __repr__(self):
        return f'<DealStage {self.name}>'

    def to_dict(self):
        """Convert stage to dictionary"""
        return {
            'id': self.id,
            'pipeline_id': self.pipeline_id,
            'name': self.name,
            'position': self.position,
            'color': self.color,
            'probability': self.probability,
            'is_closed_won': self.is_closed_won,
            'is_closed_lost': self.is_closed_lost,
            'expected_duration_days': self.expected_duration_days,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deal_count': self.deals.count()
        }
