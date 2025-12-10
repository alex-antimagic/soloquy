"""
PTO Request Model
Tracks paid time off requests and approvals
"""
from datetime import datetime, date, timedelta
from app import db


class PTORequest(db.Model):
    """PTO request model for time-off management"""
    __tablename__ = 'pto_requests'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Request details
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    total_days = db.Column(db.Float, nullable=False)  # Business days
    request_type = db.Column(db.String(50), nullable=False, default='pto')  # pto, sick, personal, unpaid

    # Status and approval
    status = db.Column(db.String(50), nullable=False, default='pending', index=True)  # pending, approved, denied, cancelled
    request_reason = db.Column(db.Text)

    # Approval tracking
    approved_by = db.Column(db.String(200))
    approved_at = db.Column(db.DateTime)
    denied_by = db.Column(db.String(200))
    denied_at = db.Column(db.DateTime)
    denial_reason = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    employee = db.relationship('Employee', back_populates='pto_requests')
    tenant = db.relationship('Tenant', backref=db.backref('pto_requests', lazy='dynamic'))

    def __repr__(self):
        return f'<PTORequest {self.id}: {self.start_date} to {self.end_date}>'

    @staticmethod
    def calculate_business_days(start_date, end_date):
        """
        Calculate business days between two dates (excluding weekends)

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Float number of business days
        """
        if start_date > end_date:
            return 0.0

        # Count business days
        business_days = 0
        current = start_date

        while current <= end_date:
            # Monday = 0, Sunday = 6
            if current.weekday() < 5:  # Monday-Friday
                business_days += 1
            current += timedelta(days=1)

        return float(business_days)

    def approve(self, approved_by):
        """
        Approve the PTO request

        Args:
            approved_by: Name/email of approver
        """
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()

        # Update employee's PTO balance and usage
        if self.employee:
            self.employee.pto_balance -= self.total_days
            self.employee.pto_used_this_year += self.total_days

    def deny(self, denied_by, reason=None):
        """
        Deny the PTO request

        Args:
            denied_by: Name/email of person denying
            reason: Optional reason for denial
        """
        self.status = 'denied'
        self.denied_by = denied_by
        self.denied_at = datetime.utcnow()
        if reason:
            self.denial_reason = reason

    def cancel(self):
        """Cancel the PTO request"""
        old_status = self.status

        # If it was approved, restore the PTO balance
        if old_status == 'approved' and self.employee:
            self.employee.pto_balance += self.total_days
            self.employee.pto_used_this_year -= self.total_days

        self.status = 'cancelled'
