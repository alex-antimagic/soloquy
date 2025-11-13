"""
TicketComment model for ticket replies and internal notes
"""
from app import db
from datetime import datetime


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Null if from customer/system

    # Comment Properties
    author_type = db.Column(db.String(20), nullable=False, default='agent')  # agent, customer, system
    body = db.Column(db.Text, nullable=False)
    body_html = db.Column(db.Text)  # Rendered HTML version

    # Visibility & Type
    is_public = db.Column(db.Boolean, nullable=False, default=True)  # False = internal note
    is_resolution = db.Column(db.Boolean, nullable=False, default=False)  # Marks ticket as resolved

    # Email Integration
    email_message_id = db.Column(db.String(500))  # For email threading

    # Attachments stored separately in TicketAttachment model

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ticket = db.relationship('Ticket', back_populates='comments')
    author = db.relationship('User', backref=db.backref('ticket_comments', lazy='dynamic'))

    def __repr__(self):
        return f'<TicketComment {self.id} on Ticket {self.ticket_id}>'

    @property
    def author_display_name(self):
        """Get author name"""
        if self.author:
            return self.author.full_name
        if self.author_type == 'customer':
            return self.ticket.requester_display_name if self.ticket else 'Customer'
        if self.author_type == 'system':
            return 'System'
        return 'Unknown'

    @property
    def is_from_customer(self):
        """Check if comment is from customer"""
        return self.author_type == 'customer'

    @property
    def is_from_agent(self):
        """Check if comment is from agent"""
        return self.author_type == 'agent'

    @property
    def is_internal_note(self):
        """Check if this is an internal note"""
        return not self.is_public
