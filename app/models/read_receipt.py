from datetime import datetime
from app import db


class ReadReceipt(db.Model):
    """Track when users read messages"""
    __tablename__ = 'read_receipts'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = db.relationship('Message', backref='read_receipts')
    user = db.relationship('User')

    # Unique constraint: one read receipt per user per message
    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='unique_message_user_read'),
    )

    def __repr__(self):
        return f'<ReadReceipt message_id={self.message_id} user_id={self.user_id}>'
