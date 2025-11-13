from app import db
from datetime import datetime


class StatusColumn(db.Model):
    """Status columns for kanban board organization"""
    __tablename__ = 'status_columns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # For ordering columns
    color = db.Column(db.String(7))  # Hex color for column header
    is_done_column = db.Column(db.Boolean, default=False)  # Mark as "completed" column
    wip_limit = db.Column(db.Integer)  # Work-in-progress limit (optional)

    # Relationships
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tasks = db.relationship('Task', backref='status_column', lazy='dynamic',
                           order_by='Task.position')

    # Unique constraint - position must be unique within a project
    __table_args__ = (
        db.UniqueConstraint('project_id', 'position', name='unique_column_position'),
    )

    def __repr__(self):
        return f'<StatusColumn {self.id}: {self.name} (pos={self.position})>'

    def get_tasks(self, include_completed=False):
        """Get all tasks in this column"""
        query = self.tasks

        if not include_completed and not self.is_done_column:
            query = query.filter(db.text("status != 'completed'"))

        return query.order_by(db.text('position')).all()

    def get_task_count(self):
        """Get count of tasks in this column"""
        return self.tasks.count()

    def is_at_wip_limit(self):
        """Check if column is at or over WIP limit"""
        if not self.wip_limit:
            return False
        return self.get_task_count() >= self.wip_limit

    def reorder(self, new_position):
        """Move this column to a new position"""
        old_position = self.position

        if new_position == old_position:
            return

        # Get all columns in this project
        columns = StatusColumn.query.filter_by(project_id=self.project_id).order_by(StatusColumn.position).all()

        if new_position < old_position:
            # Moving left - shift columns right
            for col in columns:
                if col.id != self.id and col.position >= new_position and col.position < old_position:
                    col.position += 1
        else:
            # Moving right - shift columns left
            for col in columns:
                if col.id != self.id and col.position > old_position and col.position <= new_position:
                    col.position -= 1

        self.position = new_position
        db.session.commit()

    def add_task(self, task, position=None):
        """Add a task to this column at a specific position"""
        if position is None:
            # Add to end
            max_position = db.session.query(db.func.max(db.text('position'))).filter(
                db.text(f"status_column_id = {self.id}")
            ).scalar() or 0
            position = max_position + 1

        task.status_column_id = self.id
        task.position = position

        # Auto-mark as completed if this is a done column
        if self.is_done_column:
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
        else:
            # Set status based on column (smart defaults)
            if position == 0 or 'to do' in self.name.lower() or 'backlog' in self.name.lower():
                task.status = 'pending'
            else:
                task.status = 'in_progress'

        db.session.commit()

    @staticmethod
    def create_default_columns(project_id):
        """Create default status columns for a new project"""
        default_columns = [
            {'name': 'To Do', 'position': 0, 'color': '#6B7280', 'is_done_column': False},
            {'name': 'In Progress', 'position': 1, 'color': '#3B82F6', 'is_done_column': False},
            {'name': 'Done', 'position': 2, 'color': '#10B981', 'is_done_column': True},
        ]

        columns = []
        for col_data in default_columns:
            column = StatusColumn(
                project_id=project_id,
                **col_data
            )
            db.session.add(column)
            columns.append(column)

        db.session.commit()
        return columns

    def to_dict(self):
        """Convert column to dictionary for JSON responses"""
        return {
            'id': self.id,
            'name': self.name,
            'position': self.position,
            'color': self.color,
            'is_done_column': self.is_done_column,
            'wip_limit': self.wip_limit,
            'task_count': self.get_task_count(),
            'is_at_wip_limit': self.is_at_wip_limit(),
            'project_id': self.project_id
        }
