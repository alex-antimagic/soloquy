from app import db
from datetime import datetime


class Project(db.Model):
    """Project model for organizing tasks in kanban boards"""
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#3B82F6')  # Hex color
    icon = db.Column(db.String(50))  # Emoji or icon class
    is_archived = db.Column(db.Boolean, default=False)

    # Relationships
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))  # Optional department association
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='projects')
    department = db.relationship('Department', backref='projects')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='owned_projects')
    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    status_columns = db.relationship('StatusColumn', backref='project', lazy='dynamic',
                                    order_by='StatusColumn.position',
                                    cascade='all, delete-orphan')
    members = db.relationship('ProjectMember', backref='project', lazy='dynamic',
                             cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Project {self.id}: {self.name}>'

    def get_active_tasks(self, include_completed=False):
        """Get active tasks for this project"""
        query = self.tasks

        if not include_completed:
            query = query.filter_by(status='pending').union(
                self.tasks.filter_by(status='in_progress')
            )

        return query.order_by(db.text('position')).all()

    def get_members(self):
        """Get all members of this project"""
        return [pm.user for pm in self.members.all()]

    def get_member_role(self, user_id):
        """Get a user's role in this project"""
        member = self.members.filter_by(user_id=user_id).first()
        return member.role if member else None

    def add_member(self, user_id, role='editor'):
        """Add a member to this project"""
        existing = self.members.filter_by(user_id=user_id).first()
        if existing:
            existing.role = role
        else:
            member = ProjectMember(project_id=self.id, user_id=user_id, role=role)
            db.session.add(member)
        db.session.commit()

    def remove_member(self, user_id):
        """Remove a member from this project"""
        member = self.members.filter_by(user_id=user_id).first()
        if member:
            db.session.delete(member)
            db.session.commit()

    def archive(self):
        """Archive this project"""
        self.is_archived = True
        db.session.commit()

    def unarchive(self):
        """Unarchive this project"""
        self.is_archived = False
        db.session.commit()

    def get_column_by_position(self, position):
        """Get status column by position"""
        return self.status_columns.filter_by(position=position).first()

    def get_task_count(self, include_completed=False):
        """Get count of tasks in this project"""
        query = self.tasks
        if not include_completed:
            query = query.filter(db.or_(
                db.text("status = 'pending'"),
                db.text("status = 'in_progress'")
            ))
        return query.count()

    def to_dict(self):
        """Convert project to dictionary for JSON responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'is_archived': self.is_archived,
            'owner_id': self.owner_id,
            'department': self.department.name if self.department else None,
            'task_count': self.get_task_count(),
            'member_count': self.members.count(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class ProjectMember(db.Model):
    """Association table for project members with roles"""
    __tablename__ = 'project_members'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='editor')  # owner, editor, viewer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='project_memberships')

    # Unique constraint - user can only be a member once per project
    __table_args__ = (
        db.UniqueConstraint('project_id', 'user_id', name='unique_project_member'),
    )

    def __repr__(self):
        return f'<ProjectMember project={self.project_id} user={self.user_id} role={self.role}>'
