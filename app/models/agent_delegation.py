from datetime import datetime
from app import db


class AgentDelegation(db.Model):
    """
    Track orchestrator agent delegations to specialist agents.

    This provides:
    - Audit trail of which specialists were consulted
    - Analytics on delegation patterns
    - Debugging information for improving orchestration
    """
    __tablename__ = 'agent_delegations'

    id = db.Column(db.Integer, primary_key=True)

    # Which orchestrator agent made the delegation
    orchestrator_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)

    # Which specialist agent was consulted
    specialist_id = db.Column(db.Integer, db.ForeignKey('agent.id'), nullable=False)

    # Optional: Link to the message that triggered this delegation
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)

    # The query passed to the specialist
    user_query = db.Column(db.Text, nullable=True)

    # Why this specialist was chosen (for analytics)
    delegation_reasoning = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    orchestrator = db.relationship('Agent', foreign_keys=[orchestrator_id], backref='delegations_made')
    specialist = db.relationship('Agent', foreign_keys=[specialist_id], backref='delegations_received')
    message = db.relationship('Message', foreign_keys=[message_id], backref='delegations')

    def __repr__(self):
        return f'<AgentDelegation orchestrator={self.orchestrator_id} specialist={self.specialist_id}>'
