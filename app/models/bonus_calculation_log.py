"""
Bonus Calculation Log Model
Audit trail for all bonus calculation runs
"""
from datetime import datetime
import json
from app import db


class BonusCalculationLog(db.Model):
    """Audit log for bonus calculation runs"""
    __tablename__ = 'bonus_calculation_logs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    financial_metrics_id = db.Column(db.Integer,
                                     db.ForeignKey('monthly_financial_metrics.id', ondelete='CASCADE'),
                                     nullable=False, index=True)

    # Calculation metadata
    calculation_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    triggered_by = db.Column(db.String(50), nullable=False, default='manual_admin')
    # Types: 'auto_cron', 'manual_admin', 'api_trigger'

    triggered_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Calculation results
    rules_evaluated = db.Column(db.Integer, default=0)  # Total rules checked
    rules_passed = db.Column(db.Integer, default=0)  # Rules that passed threshold
    employees_eligible = db.Column(db.Integer, default=0)  # Employees who met criteria
    bonuses_created = db.Column(db.Integer, default=0)  # CompensationChange records created
    total_bonus_amount = db.Column(db.Numeric(15, 2), default=0.0)  # Total bonus $ amount

    # Status
    status = db.Column(db.String(50), nullable=False, default='completed')
    # Statuses: 'completed', 'partial', 'failed', 'no_rules', 'no_data'

    # Detailed results (JSON)
    calculation_details = db.Column(db.Text)
    # Example: {
    #   "passed_rules": [{"rule_id": 1, "rule_name": "Revenue Threshold"}],
    #   "eligible_employees": [{"employee_id": 1, "bonus_amount": 5000}],
    #   "errors": []
    # }

    error_message = db.Column(db.Text)  # Error details if failed

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('bonus_calculation_logs', lazy='dynamic'))
    financial_metrics = db.relationship('MonthlyFinancialMetrics', back_populates='bonus_calculation_logs')
    triggered_by_user = db.relationship('User', foreign_keys=[triggered_by_user_id])
    compensation_changes = db.relationship('CompensationChange', back_populates='calculation_log',
                                          lazy='dynamic')

    def __repr__(self):
        return f'<BonusCalculationLog {self.id} - {self.calculation_date}>'

    def get_calculation_details(self):
        """Get calculation details as Python dict"""
        if not self.calculation_details:
            return {}
        try:
            return json.loads(self.calculation_details)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_calculation_details(self, details_dict):
        """Set calculation details from Python dict"""
        self.calculation_details = json.dumps(details_dict)

    def add_error(self, error_message):
        """Add an error to the calculation details"""
        details = self.get_calculation_details()
        if 'errors' not in details:
            details['errors'] = []
        details['errors'].append({
            'message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.set_calculation_details(details)

    def add_passed_rule(self, rule_id, rule_name, metric_value, threshold):
        """Add a passed rule to the calculation details"""
        details = self.get_calculation_details()
        if 'passed_rules' not in details:
            details['passed_rules'] = []
        details['passed_rules'].append({
            'rule_id': rule_id,
            'rule_name': rule_name,
            'metric_value': float(metric_value) if metric_value else 0.0,
            'threshold': float(threshold) if threshold else 0.0
        })
        self.set_calculation_details(details)

    def add_eligible_employee(self, employee_id, employee_name, bonus_amount):
        """Add an eligible employee to the calculation details"""
        details = self.get_calculation_details()
        if 'eligible_employees' not in details:
            details['eligible_employees'] = []
        details['eligible_employees'].append({
            'employee_id': employee_id,
            'employee_name': employee_name,
            'bonus_amount': float(bonus_amount) if bonus_amount else 0.0
        })
        self.set_calculation_details(details)

    @property
    def period_label(self):
        """Get formatted period label from financial metrics"""
        if self.financial_metrics:
            return self.financial_metrics.period_label
        return 'Unknown Period'

    @property
    def success_rate(self):
        """Calculate success rate of bonus creation"""
        if self.employees_eligible == 0:
            return 0.0
        return (self.bonuses_created / self.employees_eligible) * 100

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'financial_metrics_id': self.financial_metrics_id,
            'period_label': self.period_label,
            'calculation_date': self.calculation_date.isoformat(),
            'triggered_by': self.triggered_by,
            'triggered_by_user_id': self.triggered_by_user_id,
            'rules_evaluated': self.rules_evaluated,
            'rules_passed': self.rules_passed,
            'employees_eligible': self.employees_eligible,
            'bonuses_created': self.bonuses_created,
            'total_bonus_amount': float(self.total_bonus_amount) if self.total_bonus_amount else 0.0,
            'status': self.status,
            'calculation_details': self.get_calculation_details(),
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'success_rate': self.success_rate
        }
