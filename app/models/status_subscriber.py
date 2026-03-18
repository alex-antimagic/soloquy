from datetime import datetime
from app import db
import secrets


class StatusSubscriber(db.Model):
    """Email subscribers for status updates"""
    __tablename__ = 'status_subscribers'

    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('status_page_configs.id'),
                         nullable=False, index=True)

    # Subscriber Info
    email = db.Column(db.String(255), nullable=False, index=True)

    # Subscription Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmation_token = db.Column(db.String(100), unique=True, index=True)
    confirmed_at = db.Column(db.DateTime)

    # Unsubscribe
    unsubscribe_token = db.Column(db.String(100), unique=True, index=True)
    unsubscribed_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    config = db.relationship('StatusPageConfig', back_populates='subscribers')

    __table_args__ = (
        db.UniqueConstraint('config_id', 'email', name='unique_subscriber_per_config'),
    )

    def __repr__(self):
        return f'<StatusSubscriber {self.email}>'

    def generate_tokens(self):
        """Generate confirmation and unsubscribe tokens"""
        self.confirmation_token = secrets.token_urlsafe(32)
        self.unsubscribe_token = secrets.token_urlsafe(32)
