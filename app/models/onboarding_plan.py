"""
Onboarding Plan Models
Tracks onboarding plans and tasks for new hires
"""
from datetime import datetime, date
from app import db


class OnboardingPlan(db.Model):
    """Onboarding plan model for new employee onboarding"""
    __tablename__ = 'onboarding_plans'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Plan details
    start_date = db.Column(db.Date, nullable=False)
    template = db.Column(db.String(50))  # standard, engineering, sales, manager, custom
    buddy_email = db.Column(db.String(255))  # Optional onboarding buddy/mentor

    # Progress tracking
    completion_percentage = db.Column(db.Float, default=0.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    employee = db.relationship('Employee', back_populates='onboarding_plan')
    tenant = db.relationship('Tenant', backref=db.backref('onboarding_plans', lazy='dynamic'))
    tasks = db.relationship('OnboardingTask', back_populates='plan', lazy='dynamic',
                           cascade='all, delete-orphan', order_by='OnboardingTask.position')

    def __repr__(self):
        return f'<OnboardingPlan for Employee {self.employee_id}>'

    def get_tasks_summary(self):
        """
        Get summary of tasks

        Returns:
            Dict with task counts by status
        """
        all_tasks = self.tasks.all()
        total = len(all_tasks)
        completed = sum(1 for task in all_tasks if task.is_completed)
        pending = total - completed
        overdue = sum(1 for task in all_tasks if task.is_overdue and not task.is_completed)

        return {
            'total': total,
            'completed': completed,
            'pending': pending,
            'overdue': overdue
        }

    def get_overdue_tasks(self):
        """Get all overdue incomplete tasks"""
        return [task for task in self.tasks.all() if task.is_overdue and not task.is_completed]

    def calculate_completion(self):
        """
        Calculate and update completion percentage

        Returns:
            Float percentage (0-100)
        """
        summary = self.get_tasks_summary()
        if summary['total'] == 0:
            self.completion_percentage = 0.0
        else:
            self.completion_percentage = (summary['completed'] / summary['total']) * 100

        return self.completion_percentage


class OnboardingTask(db.Model):
    """Onboarding task model for checklist items"""
    __tablename__ = 'onboarding_tasks'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('onboarding_plans.id', ondelete='CASCADE'), nullable=False, index=True)

    # Task details
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    assigned_to_email = db.Column(db.String(255))
    category = db.Column(db.String(50))  # admin, it, orientation, training, feedback, custom

    # Completion tracking
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime)
    completed_by_email = db.Column(db.String(255))

    # Ordering
    position = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    plan = db.relationship('OnboardingPlan', back_populates='tasks')

    def __repr__(self):
        return f'<OnboardingTask {self.title}>'

    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if not self.due_date or self.is_completed:
            return False
        return self.due_date < date.today()

    def mark_completed(self, completed_by_email=None):
        """
        Mark task as completed

        Args:
            completed_by_email: Email of person completing the task
        """
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        if completed_by_email:
            self.completed_by_email = completed_by_email

        # Update plan completion percentage
        if self.plan:
            self.plan.calculate_completion()
