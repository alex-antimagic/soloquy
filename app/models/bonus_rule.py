"""
Bonus Rule Model
Configurable KPI rules for bonus eligibility
"""
from datetime import datetime, date
import json
from app import db


class BonusRule(db.Model):
    """Configurable KPI rules for automatic bonus calculation"""
    __tablename__ = 'bonus_rules'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Rule identification
    rule_name = db.Column(db.String(200), nullable=False)
    rule_type = db.Column(db.String(100), nullable=False, default='revenue_threshold')
    # Types: 'revenue_threshold', 'profit_margin', 'revenue_growth', 'custom'

    # Rule configuration (JSON)
    rule_config = db.Column(db.Text, nullable=False)
    # Example: {"metric": "net_revenue", "operator": ">=", "threshold": 300000}

    # Bonus calculation settings
    bonus_type = db.Column(db.String(50), nullable=False, default='performance')
    # Types: 'performance', 'annual', 'quarterly', 'spot', 'retention'

    use_employee_target_percentage = db.Column(db.Boolean, default=True, nullable=False)
    # If True, use employee.bonus_target_percentage; if False, use fixed_bonus_amount

    fixed_bonus_amount = db.Column(db.Numeric(12, 2), nullable=True)
    # Alternative to percentage-based bonus

    # Eligibility filters
    eligible_departments = db.Column(db.Text)  # JSON array of department names
    eligible_roles = db.Column(db.Text)  # JSON array of role patterns
    minimum_tenure_days = db.Column(db.Integer, default=0)  # Minimum days employed
    applies_to_all_employees = db.Column(db.Boolean, default=True, nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    effective_from = db.Column(db.Date, nullable=True)
    effective_until = db.Column(db.Date, nullable=True)

    # Metadata
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('bonus_rules', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    compensation_changes = db.relationship('CompensationChange', back_populates='kpi_rule',
                                          lazy='dynamic')

    def __repr__(self):
        return f'<BonusRule {self.rule_name}>'

    def get_rule_config(self):
        """Get rule configuration as Python dict"""
        if not self.rule_config:
            return {}
        try:
            return json.loads(self.rule_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_rule_config(self, config_dict):
        """Set rule configuration from Python dict"""
        self.rule_config = json.dumps(config_dict)

    def get_eligible_departments(self):
        """Get eligible departments as Python list"""
        if not self.eligible_departments:
            return []
        try:
            return json.loads(self.eligible_departments)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_eligible_departments(self, departments_list):
        """Set eligible departments from Python list"""
        self.eligible_departments = json.dumps(departments_list) if departments_list else None

    def get_eligible_roles(self):
        """Get eligible roles as Python list"""
        if not self.eligible_roles:
            return []
        try:
            return json.loads(self.eligible_roles)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_eligible_roles(self, roles_list):
        """Set eligible roles from Python list"""
        self.eligible_roles = json.dumps(roles_list) if roles_list else None

    def is_effective_on(self, check_date=None):
        """
        Check if rule is effective on a given date.

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            True if rule is effective on the date
        """
        if not self.is_active:
            return False

        if check_date is None:
            check_date = date.today()

        if self.effective_from and check_date < self.effective_from:
            return False

        if self.effective_until and check_date > self.effective_until:
            return False

        return True

    def evaluate_metric(self, metric_value):
        """
        Evaluate if a metric value passes this rule.

        Args:
            metric_value: The metric value to evaluate (e.g., net_revenue amount)

        Returns:
            True if the metric passes the rule threshold
        """
        config = self.get_rule_config()

        if not config:
            return False

        operator = config.get('operator', '>=')
        threshold = config.get('threshold', 0)

        try:
            metric_value = float(metric_value or 0)
            threshold = float(threshold)

            if operator == '>=':
                return metric_value >= threshold
            elif operator == '>':
                return metric_value > threshold
            elif operator == '<=':
                return metric_value <= threshold
            elif operator == '<':
                return metric_value < threshold
            elif operator == '==':
                return metric_value == threshold
            else:
                return False

        except (ValueError, TypeError):
            return False

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'rule_name': self.rule_name,
            'rule_type': self.rule_type,
            'rule_config': self.get_rule_config(),
            'bonus_type': self.bonus_type,
            'use_employee_target_percentage': self.use_employee_target_percentage,
            'fixed_bonus_amount': float(self.fixed_bonus_amount) if self.fixed_bonus_amount else None,
            'eligible_departments': self.get_eligible_departments(),
            'eligible_roles': self.get_eligible_roles(),
            'minimum_tenure_days': self.minimum_tenure_days,
            'applies_to_all_employees': self.applies_to_all_employees,
            'is_active': self.is_active,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_until': self.effective_until.isoformat() if self.effective_until else None,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @staticmethod
    def create_default_revenue_rule(tenant_id, created_by_user_id=None):
        """
        Create the default $300k monthly revenue threshold rule.

        Args:
            tenant_id: Tenant ID
            created_by_user_id: User who created the rule

        Returns:
            Created BonusRule object
        """
        rule = BonusRule(
            tenant_id=tenant_id,
            rule_name="Monthly Revenue Threshold - $300k",
            rule_type="revenue_threshold",
            rule_config=json.dumps({
                "metric": "net_revenue",
                "operator": ">=",
                "threshold": 300000
            }),
            bonus_type="performance",
            use_employee_target_percentage=True,
            applies_to_all_employees=True,
            is_active=True,
            created_by_user_id=created_by_user_id,
            description="Automatic monthly bonus when net revenue exceeds $300,000"
        )
        db.session.add(rule)
        return rule
