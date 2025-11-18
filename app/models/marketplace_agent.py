from datetime import datetime
import json
from app import db


class MarketplaceAgent(db.Model):
    """Published agents available in the marketplace"""
    __tablename__ = 'marketplace_agents'

    id = db.Column(db.Integer, primary_key=True)
    published_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Visibility: NULL = global (public to all), tenant_id = workspace-only
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)

    # Agent configuration (snapshot at publish time)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))
    system_prompt = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(50), default='claude-haiku-4-5-20251001')
    temperature = db.Column(db.Float, default=1.0)
    max_tokens = db.Column(db.Integer, default=4096)

    # Categorization
    category = db.Column(db.String(50), index=True)  # sales, support, finance, marketing, general, etc.
    tags = db.Column(db.Text)  # JSON array of tags for filtering

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Metrics
    install_count = db.Column(db.Integer, default=0, nullable=False)
    average_rating = db.Column(db.Float, default=0.0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    published_by = db.relationship('User', foreign_keys=[published_by_id])
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id])
    reviews = db.relationship('AgentReview', back_populates='marketplace_agent',
                             cascade='all, delete-orphan', lazy='dynamic')
    installs = db.relationship('AgentInstall', back_populates='marketplace_agent',
                              cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f'<MarketplaceAgent {self.name}>'

    def get_tags(self):
        """Parse tags from JSON"""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []

    def set_tags(self, tag_list):
        """Store tags as JSON"""
        self.tags = json.dumps(tag_list) if tag_list else None

    def to_dict(self):
        """Convert to dictionary for API/JSON responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'avatar_url': self.avatar_url,
            'system_prompt': self.system_prompt,
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'category': self.category,
            'tags': self.get_tags(),
            'is_featured': self.is_featured,
            'install_count': self.install_count,
            'average_rating': self.average_rating,
            'review_count': self.review_count,
            'published_by': {
                'id': self.published_by.id,
                'name': self.published_by.full_name
            } if self.published_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def update_rating_stats(self):
        """Recalculate average rating and review count"""
        from app.models.agent_review import AgentReview

        reviews = AgentReview.query.filter_by(
            marketplace_agent_id=self.id,
            is_active=True
        ).all()

        if reviews:
            self.review_count = len(reviews)
            self.average_rating = sum(r.rating for r in reviews) / len(reviews)
        else:
            self.review_count = 0
            self.average_rating = 0.0

        db.session.commit()

    @staticmethod
    def create_from_agent(agent, published_by_user, category=None, tags=None, is_public=True):
        """
        Create marketplace listing from an existing agent

        Args:
            agent: Agent instance to publish
            published_by_user: User publishing the agent
            category: Optional category (auto-detected if None)
            tags: Optional list of tags
            is_public: If True, published globally. If False, workspace-only

        Returns:
            MarketplaceAgent instance
        """
        marketplace_agent = MarketplaceAgent(
            published_by_id=published_by_user.id,
            tenant_id=None if is_public else agent.department.tenant_id,
            name=agent.name,
            description=agent.description,
            avatar_url=agent.avatar_url,
            system_prompt=agent.system_prompt,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            category=category or 'general'
        )

        if tags:
            marketplace_agent.set_tags(tags)

        db.session.add(marketplace_agent)
        db.session.commit()

        return marketplace_agent


class AgentReview(db.Model):
    """User reviews and ratings for marketplace agents"""
    __tablename__ = 'agent_reviews'

    id = db.Column(db.Integer, primary_key=True)
    marketplace_agent_id = db.Column(db.Integer, db.ForeignKey('marketplace_agents.id'),
                                     nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Review content
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review_text = db.Column(db.Text)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Can be moderated

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    marketplace_agent = db.relationship('MarketplaceAgent', back_populates='reviews')
    user = db.relationship('User', foreign_keys=[user_id])
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id])

    def __repr__(self):
        return f'<AgentReview {self.marketplace_agent.name} - {self.rating} stars>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'rating': self.rating,
            'review_text': self.review_text,
            'user': {
                'id': self.user.id,
                'name': self.user.full_name
            } if self.user else None,
            'tenant': {
                'id': self.tenant.id,
                'name': self.tenant.name
            } if self.tenant else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AgentInstall(db.Model):
    """Track agent installations from marketplace"""
    __tablename__ = 'agent_installs'

    id = db.Column(db.Integer, primary_key=True)
    marketplace_agent_id = db.Column(db.Integer, db.ForeignKey('marketplace_agents.id'),
                                     nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)  # Created agent

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    marketplace_agent = db.relationship('MarketplaceAgent', back_populates='installs')
    user = db.relationship('User', foreign_keys=[user_id])
    tenant = db.relationship('Tenant', foreign_keys=[tenant_id])
    agent = db.relationship('Agent', foreign_keys=[agent_id])

    def __repr__(self):
        return f'<AgentInstall {self.marketplace_agent.name} by {self.user.full_name}>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'marketplace_agent_id': self.marketplace_agent_id,
            'agent_id': self.agent_id,
            'installed_by': {
                'id': self.user.id,
                'name': self.user.full_name
            } if self.user else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
