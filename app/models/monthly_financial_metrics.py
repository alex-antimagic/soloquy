"""
Monthly Financial Metrics Model
Stores monthly aggregated financial data for KPI tracking and bonus calculations
"""
from datetime import datetime
from app import db


class MonthlyFinancialMetrics(db.Model):
    """Monthly financial metrics for revenue tracking and bonus calculations"""
    __tablename__ = 'monthly_financial_metrics'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)

    # Time period
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)  # 1-12

    # Financial data
    total_revenue = db.Column(db.Numeric(15, 2), default=0.0)
    total_expenses = db.Column(db.Numeric(15, 2), default=0.0)
    net_revenue = db.Column(db.Numeric(15, 2), default=0.0)
    gross_profit = db.Column(db.Numeric(15, 2), default=0.0)

    # Data source tracking
    data_source = db.Column(db.String(50), nullable=False, default='manual')  # 'quickbooks', 'manual', 'crm_deals'

    # Status
    is_finalized = db.Column(db.Boolean, default=False, nullable=False)  # Lock from further editing
    bonus_calculation_triggered = db.Column(db.Boolean, default=False, nullable=False)  # Prevent duplicate bonuses

    # Sync metadata
    quickbooks_synced_at = db.Column(db.DateTime, nullable=True)
    manual_entry_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes = db.Column(db.Text)  # Admin notes about the metrics

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('financial_metrics', lazy='dynamic'))
    manual_entry_by = db.relationship('User', foreign_keys=[manual_entry_by_user_id])
    bonus_calculation_logs = db.relationship('BonusCalculationLog', back_populates='financial_metrics',
                                            lazy='dynamic', cascade='all, delete-orphan')

    # Unique constraint: one record per tenant per month
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'year', 'month', name='unique_tenant_month_metrics'),
    )

    def __repr__(self):
        return f'<MonthlyFinancialMetrics {self.year}-{self.month:02d} Tenant={self.tenant_id}>'

    @property
    def period_label(self):
        """Get formatted period label like 'January 2024'"""
        from datetime import date
        try:
            dt = date(self.year, self.month, 1)
            return dt.strftime('%B %Y')
        except ValueError:
            return f'{self.year}-{self.month:02d}'

    @property
    def period_short(self):
        """Get short period label like 'Jan 2024'"""
        from datetime import date
        try:
            dt = date(self.year, self.month, 1)
            return dt.strftime('%b %Y')
        except ValueError:
            return f'{self.year}-{self.month:02d}'

    def calculate_net_revenue(self):
        """Calculate net revenue from total revenue and expenses"""
        self.net_revenue = (self.total_revenue or 0) - (self.total_expenses or 0)
        return self.net_revenue

    def calculate_gross_profit(self):
        """Calculate gross profit (for now, same as net revenue - could be refined)"""
        self.gross_profit = self.net_revenue
        return self.gross_profit

    def finalize(self, user_id=None):
        """
        Finalize metrics to prevent further editing.

        Args:
            user_id: User ID who finalized the metrics
        """
        self.is_finalized = True
        if user_id:
            self.manual_entry_by_user_id = user_id
        self.updated_at = datetime.utcnow()

    def unfinalize(self):
        """Allow editing of metrics again"""
        self.is_finalized = False
        self.updated_at = datetime.utcnow()

    @staticmethod
    def get_or_create(tenant_id, year, month):
        """
        Get existing metrics or create new record.

        Args:
            tenant_id: Tenant ID
            year: Year (e.g., 2024)
            month: Month (1-12)

        Returns:
            Tuple of (metrics, created) where created is True if new record
        """
        metrics = MonthlyFinancialMetrics.query.filter_by(
            tenant_id=tenant_id,
            year=year,
            month=month
        ).first()

        if metrics:
            return metrics, False

        # Create new metrics record
        metrics = MonthlyFinancialMetrics(
            tenant_id=tenant_id,
            year=year,
            month=month,
            total_revenue=0.0,
            total_expenses=0.0,
            net_revenue=0.0,
            gross_profit=0.0,
            data_source='manual'
        )
        db.session.add(metrics)

        return metrics, True

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'year': self.year,
            'month': self.month,
            'period_label': self.period_label,
            'total_revenue': float(self.total_revenue) if self.total_revenue else 0.0,
            'total_expenses': float(self.total_expenses) if self.total_expenses else 0.0,
            'net_revenue': float(self.net_revenue) if self.net_revenue else 0.0,
            'gross_profit': float(self.gross_profit) if self.gross_profit else 0.0,
            'data_source': self.data_source,
            'is_finalized': self.is_finalized,
            'bonus_calculation_triggered': self.bonus_calculation_triggered,
            'quickbooks_synced_at': self.quickbooks_synced_at.isoformat() if self.quickbooks_synced_at else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
