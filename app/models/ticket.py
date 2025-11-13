"""
Ticket model for support ticketing system
"""
from app import db
from datetime import datetime
from sqlalchemy import Index


class Ticket(db.Model):
    __tablename__ = 'tickets'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Multi-tenancy
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Ticket Identifier
    ticket_number = db.Column(db.String(50), nullable=False, index=True)  # e.g., TKT-00001

    # Core Content
    subject = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)

    # Status & Priority
    status = db.Column(db.String(50), nullable=False, default='new', index=True)  # new, open, pending, on_hold, resolved, closed
    priority = db.Column(db.String(20), nullable=False, default='medium')  # low, medium, high, urgent

    # Categorization
    category = db.Column(db.String(100))  # Technical Support, Billing, Feature Request, etc.
    source = db.Column(db.String(50), default='web')  # email, web, api, chat, phone, portal
    tags = db.Column(db.String(500))  # Comma-separated tags

    # Relationships - Foreign Keys
    requester_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), index=True)  # Customer who submitted
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), index=True)  # Associated company
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # Assigned agent
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), index=True)  # Routing department
    related_ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'))  # Linked/merged tickets

    # Email Integration (for non-registered contacts)
    requester_email = db.Column(db.String(255))  # Email address if no contact
    requester_name = db.Column(db.String(200))  # Name if no contact
    email_message_id = db.Column(db.String(500))  # Original email ID for threading

    # SLA Tracking
    first_response_at = db.Column(db.DateTime)  # When first reply was sent
    first_response_due_at = db.Column(db.DateTime)  # SLA deadline for first response
    resolution_due_at = db.Column(db.DateTime)  # SLA deadline for resolution
    resolved_at = db.Column(db.DateTime)  # When marked as resolved
    closed_at = db.Column(db.DateTime)  # When closed

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)  # Any comment/update

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('tickets', lazy='dynamic'))
    requester = db.relationship('Contact', foreign_keys=[requester_id], backref=db.backref('tickets', lazy='dynamic'))
    company = db.relationship('Company', foreign_keys=[company_id], backref=db.backref('tickets', lazy='dynamic'))
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref=db.backref('assigned_tickets', lazy='dynamic'))
    department = db.relationship('Department', foreign_keys=[department_id], backref=db.backref('tickets', lazy='dynamic'))
    related_ticket = db.relationship('Ticket', remote_side=[id], backref='related_tickets', uselist=False)

    comments = db.relationship('TicketComment', back_populates='ticket', lazy='dynamic', cascade='all, delete-orphan', order_by='TicketComment.created_at')
    attachments = db.relationship('TicketAttachment', back_populates='ticket', lazy='dynamic', cascade='all, delete-orphan')
    status_history = db.relationship('TicketStatusHistory', back_populates='ticket', lazy='dynamic', cascade='all, delete-orphan', order_by='TicketStatusHistory.created_at.desc()')

    # Table constraints
    __table_args__ = (
        Index('idx_tenant_ticket_number', 'tenant_id', 'ticket_number', unique=True),
        Index('idx_tenant_status', 'tenant_id', 'status'),
        Index('idx_tenant_created', 'tenant_id', 'created_at'),
    )

    def __repr__(self):
        return f'<Ticket {self.ticket_number}: {self.subject}>'

    @property
    def is_overdue(self):
        """Check if ticket is overdue based on resolution SLA"""
        if self.resolution_due_at and self.status not in ['resolved', 'closed']:
            return datetime.utcnow() > self.resolution_due_at
        return False

    @property
    def is_awaiting_first_response(self):
        """Check if ticket needs first response"""
        return not self.first_response_at and self.status not in ['resolved', 'closed']

    @property
    def requester_display_name(self):
        """Get requester name - either from contact or from stored name"""
        if self.requester:
            return f"{self.requester.first_name} {self.requester.last_name}"
        return self.requester_name or 'Unknown'

    @property
    def requester_display_email(self):
        """Get requester email - either from contact or from stored email"""
        if self.requester:
            return self.requester.email
        return self.requester_email

    @property
    def public_comments(self):
        """Get only public comments"""
        return self.comments.filter_by(is_public=True).all()

    @property
    def internal_notes(self):
        """Get only internal notes"""
        return self.comments.filter_by(is_public=False).all()

    @property
    def comment_count(self):
        """Total number of comments"""
        return self.comments.count()

    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def set_tags_list(self, tags_list):
        """Set tags from a list"""
        self.tags = ', '.join(tags_list) if tags_list else None
