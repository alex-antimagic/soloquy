"""
TicketAttachment model for file attachments on tickets
"""
from app import db
from datetime import datetime


class TicketAttachment(db.Model):
    __tablename__ = 'ticket_attachments'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('ticket_comments.id'))  # Optional - which comment uploaded this
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Who uploaded

    # File Information
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # Storage location (S3, local, etc.)
    file_size = db.Column(db.Integer)  # Size in bytes
    content_type = db.Column(db.String(100))  # MIME type (image/png, application/pdf, etc.)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    ticket = db.relationship('Ticket', back_populates='attachments')
    comment = db.relationship('TicketComment', backref=db.backref('attachments', lazy='dynamic'))
    uploaded_by = db.relationship('User', backref=db.backref('ticket_attachments', lazy='dynamic'))

    def __repr__(self):
        return f'<TicketAttachment {self.filename} on Ticket {self.ticket_id}>'

    @property
    def file_size_display(self):
        """Human-readable file size"""
        if not self.file_size:
            return 'Unknown'

        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    @property
    def is_image(self):
        """Check if attachment is an image"""
        if self.content_type:
            return self.content_type.startswith('image/')
        return self.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'))

    @property
    def icon_class(self):
        """Bootstrap icon class for file type"""
        if self.is_image:
            return 'bi-file-image'
        elif self.content_type and 'pdf' in self.content_type:
            return 'bi-file-pdf'
        elif self.content_type and 'word' in self.content_type:
            return 'bi-file-word'
        elif self.content_type and 'excel' in self.content_type or self.content_type and 'spreadsheet' in self.content_type:
            return 'bi-file-excel'
        elif self.content_type and 'zip' in self.content_type or self.content_type and 'compressed' in self.content_type:
            return 'bi-file-zip'
        else:
            return 'bi-file-earmark'
