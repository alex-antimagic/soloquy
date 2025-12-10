"""
Employee Model
Tracks employee records and information
"""
from datetime import datetime, date
import json
from app import db


class Employee(db.Model):
    """Employee model for HR records"""
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Employee identification
    employee_number = db.Column(db.String(50), unique=True, index=True)  # e.g., EMP-001

    # Personal information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50))

    # Employment information
    department_name = db.Column(db.String(100))
    role = db.Column(db.String(200))
    manager_name = db.Column(db.String(200))
    hire_date = db.Column(db.Date, nullable=False)
    termination_date = db.Column(db.Date)
    status = db.Column(db.String(50), nullable=False, default='active', index=True)  # active, on_leave, terminated

    # Compensation
    salary = db.Column(db.Numeric(12, 2))
    salary_currency = db.Column(db.String(3), default='USD')
    bonus_target_percentage = db.Column(db.Float)  # e.g., 10.0 for 10%

    # Time off
    pto_balance = db.Column(db.Float, default=0.0)  # Available PTO days
    pto_used_this_year = db.Column(db.Float, default=0.0)
    sick_days_balance = db.Column(db.Float, default=0.0)

    # Metadata
    notes = db.Column(db.Text)  # JSON array of HR notes
    documents = db.Column(db.Text)  # JSON array of document URLs

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('employees', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('employee_record', uselist=False))
    onboarding_plan = db.relationship('OnboardingPlan', back_populates='employee', uselist=False,
                                      cascade='all, delete-orphan')
    pto_requests = db.relationship('PTORequest', back_populates='employee', lazy='dynamic',
                                   cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Employee {self.employee_number}: {self.full_name}>'

    @property
    def full_name(self):
        """Get employee's full name"""
        return f'{self.first_name} {self.last_name}'

    @property
    def pto_scheduled_future(self):
        """Get total days of approved PTO scheduled in the future"""
        from app.models.pto_request import PTORequest

        future_requests = self.pto_requests.filter(
            PTORequest.status == 'approved',
            PTORequest.start_date >= date.today()
        ).all()

        return sum(req.total_days for req in future_requests)

    def get_performance_reviews(self):
        """Get performance reviews (placeholder - would need PerformanceReview model)"""
        # TODO: Implement when PerformanceReview model is created
        return []

    def get_hr_notes(self):
        """Get HR notes as Python list"""
        if not self.notes:
            return []
        try:
            return json.loads(self.notes)
        except (json.JSONDecodeError, TypeError):
            return []

    def add_hr_note(self, note_type, note, created_by=None, is_confidential=True):
        """
        Add an HR note

        Args:
            note_type: Type of note (general, performance, one_on_one, disciplinary, recognition)
            note: Note text
            created_by: Name/email of person creating the note
            is_confidential: Whether note is confidential (default: True)
        """
        notes_list = self.get_hr_notes()

        note_entry = {
            'type': note_type,
            'note': note,
            'date': datetime.utcnow().isoformat(),
            'created_by': created_by,
            'is_confidential': is_confidential
        }

        notes_list.append(note_entry)
        self.notes = json.dumps(notes_list)

    def get_upcoming_pto(self):
        """Get upcoming approved PTO requests"""
        from app.models.pto_request import PTORequest

        return self.pto_requests.filter(
            PTORequest.status == 'approved',
            PTORequest.start_date >= date.today()
        ).order_by(PTORequest.start_date).all()

    def calculate_pto_balance(self):
        """
        Calculate current PTO balance

        Note: This is a simplified calculation. In production, you'd want:
        - Accrual policies (monthly, bi-weekly, etc.)
        - Carry-over rules
        - Probation period rules
        """
        # For now, just return the stored balance
        return self.pto_balance

    @staticmethod
    def generate_employee_number(tenant_id):
        """
        Generate unique employee number for a tenant

        Args:
            tenant_id: Tenant ID

        Returns:
            String like 'EMP-001', 'EMP-002', etc.
        """
        # Get the highest employee number for this tenant
        last_employee = Employee.query.filter_by(tenant_id=tenant_id).order_by(
            Employee.id.desc()
        ).first()

        if not last_employee or not last_employee.employee_number:
            number = 1
        else:
            # Extract number from format like 'EMP-001'
            try:
                parts = last_employee.employee_number.split('-')
                if len(parts) == 2:
                    number = int(parts[1]) + 1
                else:
                    number = 1
            except (ValueError, IndexError):
                number = 1

        return f'EMP-{number:03d}'
