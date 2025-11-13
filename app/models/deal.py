from datetime import datetime
from app import db
from app.models.crm_associations import deal_contacts, deal_tasks


class Deal(db.Model):
    """Deal/Opportunity model - sales pipeline management"""
    __tablename__ = 'deals'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), index=True)

    # Deal Information
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(15, 2))  # Deal value
    currency = db.Column(db.String(3), default='USD')
    probability = db.Column(db.Integer, default=0)  # 0-100 chance of closing

    # Pipeline Status (Kanban-style)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('deal_pipelines.id'), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey('deal_stages.id'), nullable=False)
    position = db.Column(db.Integer, default=0)  # Position within stage for ordering

    # Deal Type
    deal_type = db.Column(db.String(50), default='new_business')  # new_business, upsell, renewal

    # Timeline
    expected_close_date = db.Column(db.Date)
    closed_date = db.Column(db.Date)

    # Status
    status = db.Column(db.String(20), default='open')  # open, won, lost, abandoned
    lost_reason = db.Column(db.String(255))

    # Tracking
    tags = db.Column(db.String(500))
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent

    # Ownership
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', backref='deals')
    company = db.relationship('Company', back_populates='deals')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_deals')
    assigned_agent = db.relationship('Agent', foreign_keys=[assigned_to_agent_id], backref='assigned_deals')
    pipeline = db.relationship('DealPipeline', back_populates='deals')
    stage = db.relationship('DealStage', back_populates='deals')
    contacts = db.relationship('Contact', secondary=deal_contacts, backref='deals')
    activities = db.relationship('Activity', back_populates='deal', lazy='dynamic')
    tasks = db.relationship('Task', secondary=deal_tasks, backref='related_deals')

    def __repr__(self):
        return f'<Deal {self.name}>'

    def get_priority_badge_class(self):
        """Get Bootstrap badge class for priority"""
        priority_classes = {
            'low': 'bg-secondary',
            'medium': 'bg-primary',
            'high': 'bg-danger',
            'urgent': 'bg-danger'
        }
        return priority_classes.get(self.priority, 'bg-secondary')

    def get_status_badge_class(self):
        """Get Bootstrap badge class for status"""
        status_classes = {
            'open': 'bg-info',
            'won': 'bg-success',
            'lost': 'bg-danger',
            'abandoned': 'bg-secondary'
        }
        return status_classes.get(self.status, 'bg-secondary')

    def move_to_stage(self, stage_id, position=None):
        """Move deal to a different stage"""
        from app import db

        # Update stage
        old_stage_id = self.stage_id
        self.stage_id = stage_id
        self.updated_at = datetime.utcnow()

        # Update position if provided
        if position is not None:
            self.position = position
        else:
            # Put at end of new stage
            max_position = db.session.query(db.func.max(Deal.position)).filter_by(stage_id=stage_id).scalar()
            self.position = (max_position or 0) + 1

        # Update status based on stage properties
        from app.models.deal_stage import DealStage
        stage = DealStage.query.get(stage_id)
        if stage:
            self.probability = stage.probability
            if stage.is_closed_won:
                self.status = 'won'
                self.closed_date = datetime.utcnow().date()
            elif stage.is_closed_lost:
                self.status = 'lost'
                self.closed_date = datetime.utcnow().date()

        db.session.commit()
        return True

    def to_dict(self):
        """Convert deal to dictionary"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'company_id': self.company_id,
            'name': self.name,
            'description': self.description,
            'amount': float(self.amount) if self.amount else None,
            'currency': self.currency,
            'probability': self.probability,
            'pipeline_id': self.pipeline_id,
            'stage_id': self.stage_id,
            'position': self.position,
            'deal_type': self.deal_type,
            'expected_close_date': self.expected_close_date.isoformat() if self.expected_close_date else None,
            'closed_date': self.closed_date.isoformat() if self.closed_date else None,
            'status': self.status,
            'lost_reason': self.lost_reason,
            'tags': self.tags,
            'priority': self.priority,
            'owner_id': self.owner_id,
            'assigned_to_agent_id': self.assigned_to_agent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'company_name': self.company.name if self.company else None,
            'stage_name': self.stage.name if self.stage else None,
            'pipeline_name': self.pipeline.name if self.pipeline else None
        }
