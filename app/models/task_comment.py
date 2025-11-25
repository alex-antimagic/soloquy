from app import db
from datetime import datetime


class TaskComment(db.Model):
    """Comments on tasks by users or agents for audit trail"""
    __tablename__ = 'task_comments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False, index=True)

    # Author can be user OR agent
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))

    # Comment content
    comment_text = db.Column(db.Text, nullable=False)
    comment_type = db.Column(db.String(50), default='note')  # note, progress_update, status_change, approval, error

    # System-generated comments (e.g., "Task approved", "Execution started")
    is_system_generated = db.Column(db.Boolean, default=False)

    # Optional metadata for system comments
    meta_data = db.Column(db.Text)  # JSON: {old_status: 'pending', new_status: 'in_progress', etc.}

    # Tenant for multi-tenancy
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    task = db.relationship('Task', backref='comments')
    user = db.relationship('User', foreign_keys=[user_id])
    agent = db.relationship('Agent', foreign_keys=[agent_id])
    tenant = db.relationship('Tenant')

    def __repr__(self):
        author = f"User {self.user_id}" if self.user_id else f"Agent {self.agent_id}"
        return f'<TaskComment {self.id}: Task {self.task_id} by {author}>'

    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        author_name = None
        author_type = None
        author_avatar = None

        if self.user_id and self.user:
            author_name = self.user.full_name
            author_type = 'user'
            author_avatar = self.user.avatar_url
        elif self.agent_id and self.agent:
            author_name = self.agent.name
            author_type = 'agent'
            author_avatar = self.agent.avatar_url

        return {
            'id': self.id,
            'task_id': self.task_id,
            'comment_text': self.comment_text,
            'comment_type': self.comment_type,
            'is_system_generated': self.is_system_generated,
            'author_name': author_name,
            'author_type': author_type,
            'author_avatar': author_avatar,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def create_comment(task_id, comment_text, user_id=None, agent_id=None,
                      comment_type='note', is_system=False, meta_data=None, tenant_id=None):
        """Helper to create a comment"""
        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            agent_id=agent_id,
            comment_text=comment_text,
            comment_type=comment_type,
            is_system_generated=is_system,
            meta_data=meta_data,
            tenant_id=tenant_id
        )
        db.session.add(comment)
        db.session.commit()
        return comment
