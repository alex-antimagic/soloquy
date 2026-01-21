"""
CompensationChange Model
Tracks salary changes, raises, and bonus adjustments over time
"""
from datetime import datetime
from app import db


class CompensationChange(db.Model):
    """Track compensation changes for employees"""
    __tablename__ = 'compensation_changes'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)

    # Change details
    change_type = db.Column(db.String(50), nullable=False, index=True)  # 'salary_change', 'bonus', 'raise', 'promotion'
    effective_date = db.Column(db.Date, nullable=False, index=True)

    # Old values (for salary changes)
    previous_salary = db.Column(db.Numeric(12, 2))
    previous_salary_currency = db.Column(db.String(3))

    # New values
    new_salary = db.Column(db.Numeric(12, 2))
    new_salary_currency = db.Column(db.String(3), default='USD')

    # Bonus information
    bonus_amount = db.Column(db.Numeric(12, 2))
    bonus_currency = db.Column(db.String(3))
    bonus_type = db.Column(db.String(50))  # 'annual', 'performance', 'signing', 'retention', 'spot'

    # Raise information
    raise_percentage = db.Column(db.Float)  # e.g., 5.0 for 5%
    raise_amount = db.Column(db.Numeric(12, 2))

    # Metadata
    reason = db.Column(db.Text)  # 'Annual review', 'Promotion to Senior Engineer', 'Market adjustment'
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='planned', index=True)  # 'planned', 'approved', 'implemented', 'cancelled'

    # Approval tracking
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    approved_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('compensation_changes', lazy='dynamic'))
    employee = db.relationship('Employee', backref=db.backref('compensation_changes', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='compensation_changes_created')
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id], backref='compensation_changes_approved')

    def __repr__(self):
        return f'<CompensationChange {self.id}: {self.change_type} for Employee {self.employee_id}>'

    @property
    def is_future(self):
        """Check if this change is in the future"""
        from datetime import date
        return self.effective_date > date.today()

    @property
    def is_pending_approval(self):
        """Check if this change is awaiting approval"""
        return self.status == 'planned'

    def approve(self, approved_by_user):
        """
        Approve this compensation change

        Args:
            approved_by_user: User object who is approving
        """
        self.status = 'approved'
        self.approved_by_user_id = approved_by_user.id
        self.approved_at = datetime.utcnow()

    def implement(self):
        """
        Mark this change as implemented and update employee record if applicable

        This should be called when the change is actually applied
        """
        self.status = 'implemented'

        # If it's a salary change, update the employee's current salary
        if self.change_type in ['salary_change', 'raise', 'promotion'] and self.new_salary:
            self.employee.salary = self.new_salary
            self.employee.salary_currency = self.new_salary_currency

    def cancel(self):
        """Cancel this planned compensation change"""
        self.status = 'cancelled'
