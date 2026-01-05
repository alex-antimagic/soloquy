"""
TaskAttachment model for file attachments on tasks
"""
from app import db
from datetime import datetime


class TaskAttachment(db.Model):
    __tablename__ = 'task_attachments'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('task_comments.id'))  # Optional - for comment attachments
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # File Information
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # Cloudinary URL
    file_size = db.Column(db.Integer)  # Size in bytes
    content_type = db.Column(db.String(100))  # MIME type

    # Cloudinary specific
    cloudinary_public_id = db.Column(db.String(255))  # For deletion

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    task = db.relationship('Task', back_populates='attachments')
    comment = db.relationship('TaskComment', backref=db.backref('attachments', lazy='dynamic'))
    uploaded_by = db.relationship('User', backref=db.backref('task_attachments', lazy='dynamic'))

    def __repr__(self):
        return f'<TaskAttachment {self.filename} on Task {self.task_id}>'

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
        return self.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))

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

    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'comment_id': self.comment_id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_size_display': self.file_size_display,
            'content_type': self.content_type,
            'is_image': self.is_image,
            'icon_class': self.icon_class,
            'uploaded_by': self.uploaded_by.full_name if self.uploaded_by else None,
            'uploaded_by_id': self.uploaded_by_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'cloudinary_public_id': self.cloudinary_public_id
        }
