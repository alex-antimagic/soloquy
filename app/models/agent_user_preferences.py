from datetime import datetime
from app import db


class AgentUserPreferences(db.Model):
    """
    Store per-user preferences for agent interactions.

    This includes:
    - Agent visibility settings (show/hide in sidebar)
    - Preferred interaction mode (orchestrator vs direct)
    """
    __tablename__ = 'agent_user_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=True)

    # Agent visibility in sidebar
    visible_in_sidebar = db.Column(db.Boolean, default=True, nullable=False)

    # User's preferred mode: 'orchestrator' or 'direct'
    preferred_mode = db.Column(db.String(20), default='orchestrator', nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref='agent_preferences')
    agent = db.relationship('Agent', backref='user_preferences')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'agent_id', name='unique_user_agent_pref'),
    )

    def __repr__(self):
        return f'<AgentUserPreferences user_id={self.user_id} agent_id={self.agent_id} mode={self.preferred_mode}>'
