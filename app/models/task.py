from app import db
from datetime import datetime


class Task(db.Model):
    """Task model for personal and team task management"""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    due_date = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Kanban fields
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))  # Nullable - tasks can exist without project
    status_column_id = db.Column(db.Integer, db.ForeignKey('status_columns.id'))  # Nullable - for backward compat
    position = db.Column(db.Integer, default=0)  # Position within column for drag-and-drop ordering
    section = db.Column(db.String(100))  # Optional grouping within project (e.g., "Frontend", "Backend")
    tags = db.Column(db.String(500))  # Comma-separated tags
    story_points = db.Column(db.Integer)  # For estimation/sprint planning
    parent_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))  # For subtasks

    # Relationships
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to_agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))  # Tasks can be assigned to agents
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))  # Optional team context

    # Long-running task execution
    is_long_running = db.Column(db.Boolean, default=False)
    execution_plan = db.Column(db.Text)  # JSON: {steps:[], estimated_duration:int, requires_approval:bool}
    execution_model = db.Column(db.String(50))  # 'claude-sonnet-4-5-...' when switched
    rq_job_id = db.Column(db.String(100), index=True)  # RQ background job ID
    queue_name = db.Column(db.String(50))  # 'high', 'default', 'low'

    # Progress tracking
    progress_percentage = db.Column(db.Integer, default=0)
    current_step = db.Column(db.String(500))
    estimated_completion = db.Column(db.DateTime)
    last_progress_update = db.Column(db.DateTime)

    # Approval workflow
    requires_approval = db.Column(db.Boolean, default=False)
    approval_status = db.Column(db.String(20))  # 'pending', 'approved', 'rejected'
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Results and errors
    execution_result = db.Column(db.Text)  # JSON: results, files generated, etc.
    execution_error = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref='tasks')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_tasks')
    assigned_to_agent = db.relationship('Agent', foreign_keys=[assigned_to_agent_id], backref='assigned_tasks')
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_tasks')
    department = db.relationship('Department', backref='tasks')
    # project relationship defined in project.py
    # status_column relationship defined in status_column.py
    parent_task = db.relationship('Task', remote_side=[id], backref='subtasks')

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'

    def mark_complete(self):
        """Mark task as completed"""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.commit()

    def mark_incomplete(self):
        """Mark task as incomplete"""
        self.status = 'pending'
        self.completed_at = None
        db.session.commit()

    def toggle_complete(self):
        """Toggle completion status"""
        if self.status == 'completed':
            self.mark_incomplete()
        else:
            self.mark_complete()
        return self.status

    def change_priority(self, new_priority):
        """Update task priority"""
        if new_priority in ['low', 'medium', 'high', 'urgent']:
            self.priority = new_priority
            db.session.commit()
            return True
        return False

    def is_overdue(self):
        """Check if task is overdue"""
        if self.due_date and self.status != 'completed':
            return datetime.utcnow() > self.due_date
        return False

    def move_to_column(self, column_id, position=None):
        """Move task to a different status column"""
        from app.models.status_column import StatusColumn

        old_column_id = self.status_column_id
        new_column = StatusColumn.query.get(column_id)

        if not new_column:
            return False

        # Update column
        self.status_column_id = column_id

        # Update position (default to end of column)
        if position is None:
            max_pos = db.session.query(db.func.max(Task.position)).filter(
                Task.status_column_id == column_id
            ).scalar() or 0
            self.position = max_pos + 1
        else:
            self.position = position

        # Auto-update status based on column type
        if new_column.is_done_column:
            self.status = 'completed'
            self.completed_at = datetime.utcnow()
        elif old_column_id != column_id:
            # Moving to non-done column
            if self.status == 'completed':
                self.status = 'in_progress'
                self.completed_at = None
            elif self.status == 'pending':
                self.status = 'in_progress'

        db.session.commit()
        return True

    def reorder_in_column(self, new_position):
        """Reorder task within its current column"""
        if not self.status_column_id:
            return False

        old_position = self.position

        if new_position == old_position:
            return True

        # Get all tasks in the same column
        tasks = Task.query.filter_by(
            status_column_id=self.status_column_id
        ).order_by(Task.position).all()

        # Adjust positions
        if new_position < old_position:
            # Moving up - shift tasks down
            for task in tasks:
                if task.id != self.id and task.position >= new_position and task.position < old_position:
                    task.position += 1
        else:
            # Moving down - shift tasks up
            for task in tasks:
                if task.id != self.id and task.position > old_position and task.position <= new_position:
                    task.position -= 1

        self.position = new_position
        db.session.commit()
        return True

    def get_subtasks(self):
        """Get all subtasks of this task"""
        return Task.query.filter_by(parent_task_id=self.id).order_by(Task.position).all()

    def get_tag_list(self):
        """Get tags as a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    def add_tag(self, tag):
        """Add a tag to this task"""
        tags = self.get_tag_list()
        if tag not in tags:
            tags.append(tag)
            self.tags = ', '.join(tags)
            db.session.commit()

    def remove_tag(self, tag):
        """Remove a tag from this task"""
        tags = self.get_tag_list()
        if tag in tags:
            tags.remove(tag)
            self.tags = ', '.join(tags) if tags else None
            db.session.commit()

    def get_priority_badge_class(self):
        """Get Bootstrap badge class for priority"""
        priority_classes = {
            'low': 'bg-secondary',
            'medium': 'bg-info',
            'high': 'bg-warning',
            'urgent': 'bg-danger'
        }
        return priority_classes.get(self.priority, 'bg-secondary')

    def get_status_badge_class(self):
        """Get Bootstrap badge class for status"""
        status_classes = {
            'pending': 'bg-secondary',
            'in_progress': 'bg-primary',
            'completed': 'bg-success'
        }
        return status_classes.get(self.status, 'bg-secondary')

    @staticmethod
    def get_user_tasks(user_id, tenant_id, limit=10, include_completed=False):
        """Get tasks assigned to a specific user (excludes agent-assigned tasks)"""
        query = Task.query.filter_by(
            assigned_to_id=user_id,
            tenant_id=tenant_id
        ).filter(Task.assigned_to_agent_id.is_(None))  # Exclude agent tasks

        if not include_completed:
            query = query.filter(Task.status != 'completed')

        return query.order_by(
            Task.due_date.asc().nullslast(),
            Task.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def get_department_tasks(department_id, tenant_id, limit=10, include_completed=False):
        """Get tasks for a specific department"""
        query = Task.query.filter_by(
            department_id=department_id,
            tenant_id=tenant_id
        )

        if not include_completed:
            query = query.filter(Task.status != 'completed')

        return query.order_by(
            Task.due_date.asc().nullslast(),
            Task.created_at.desc()
        ).limit(limit).all()

    def to_dict(self):
        """Convert task to dictionary for JSON responses"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'assigned_to': self.assigned_to.full_name if self.assigned_to else None,
            'assigned_to_agent': self.assigned_to_agent.name if self.assigned_to_agent else None,
            'created_by': self.created_by.full_name if self.created_by else None,
            'department': self.department.name if self.department else None,
            'project_id': self.project_id,
            'status_column_id': self.status_column_id,
            'position': self.position,
            'section': self.section,
            'tags': self.get_tag_list(),
            'story_points': self.story_points,
            'parent_task_id': self.parent_task_id,
            'subtask_count': len(self.get_subtasks()),
            'is_overdue': self.is_overdue(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
