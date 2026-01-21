"""
Financial Metrics Service
Handles manual entry and management of monthly financial metrics
"""
from datetime import datetime, date
from decimal import Decimal
from app import db
from app.models.monthly_financial_metrics import MonthlyFinancialMetrics
import logging

logger = logging.getLogger(__name__)


class FinancialMetricsService:
    """Service for managing monthly financial metrics"""

    @staticmethod
    def update_manual_metrics(tenant_id, year, month, revenue, expenses, user_id, notes=None):
        """
        Manual entry of financial metrics by admin.

        Args:
            tenant_id: Tenant ID
            year: Year (e.g., 2024)
            month: Month (1-12)
            revenue: Total revenue amount
            expenses: Total expenses amount
            user_id: User ID entering the data
            notes: Optional notes

        Returns:
            Updated MonthlyFinancialMetrics object
        """
        try:
            # Get or create metrics
            metrics, created = MonthlyFinancialMetrics.get_or_create(tenant_id, year, month)

            # Check if already finalized
            if metrics.is_finalized:
                raise ValueError(f"Metrics for {metrics.period_label} are finalized and cannot be edited")

            # Update values
            metrics.total_revenue = Decimal(str(revenue)) if revenue else Decimal('0.00')
            metrics.total_expenses = Decimal(str(expenses)) if expenses else Decimal('0.00')
            metrics.calculate_net_revenue()
            metrics.calculate_gross_profit()

            # Update metadata
            metrics.data_source = 'manual'
            metrics.manual_entry_by_user_id = user_id
            if notes:
                metrics.notes = notes
            metrics.updated_at = datetime.utcnow()

            db.session.commit()

            logger.info(f"Updated manual metrics for {year}-{month:02d}: Revenue=${revenue}, Expenses=${expenses}")
            return metrics

        except Exception as e:
            logger.error(f"Error updating manual metrics: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def finalize_metrics(metrics_id, user_id):
        """
        Lock metrics from further editing.

        Args:
            metrics_id: MonthlyFinancialMetrics ID
            user_id: User ID finalizing the metrics

        Returns:
            Updated metrics object
        """
        try:
            metrics = MonthlyFinancialMetrics.query.get(metrics_id)
            if not metrics:
                raise ValueError(f"Metrics {metrics_id} not found")

            metrics.finalize(user_id)
            db.session.commit()

            logger.info(f"Finalized metrics {metrics_id} for {metrics.period_label}")
            return metrics

        except Exception as e:
            logger.error(f"Error finalizing metrics: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def unfinalize_metrics(metrics_id):
        """
        Allow editing of metrics again.

        Args:
            metrics_id: MonthlyFinancialMetrics ID

        Returns:
            Updated metrics object
        """
        try:
            metrics = MonthlyFinancialMetrics.query.get(metrics_id)
            if not metrics:
                raise ValueError(f"Metrics {metrics_id} not found")

            metrics.unfinalize()
            db.session.commit()

            logger.info(f"Unfinalized metrics {metrics_id} for {metrics.period_label}")
            return metrics

        except Exception as e:
            logger.error(f"Error unfinalizing metrics: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def get_metrics_summary(tenant_id, year=None):
        """
        Get year-to-date metrics summary for dashboard.

        Args:
            tenant_id: Tenant ID
            year: Year (defaults to current year)

        Returns:
            Dict with summary data
        """
        try:
            if year is None:
                year = date.today().year

            # Get all metrics for the year
            metrics_list = MonthlyFinancialMetrics.query.filter_by(
                tenant_id=tenant_id,
                year=year
            ).order_by(MonthlyFinancialMetrics.month).all()

            total_revenue = sum(m.total_revenue or 0 for m in metrics_list)
            total_expenses = sum(m.total_expenses or 0 for m in metrics_list)
            total_net_revenue = sum(m.net_revenue or 0 for m in metrics_list)

            # Calculate average monthly revenue
            months_with_data = len([m for m in metrics_list if m.total_revenue > 0])
            avg_monthly_revenue = (
                total_revenue / months_with_data if months_with_data > 0 else 0
            )

            # Count months where bonuses were triggered
            bonus_months = len([m for m in metrics_list if m.bonus_calculation_triggered])

            summary = {
                'year': year,
                'total_revenue': float(total_revenue),
                'total_expenses': float(total_expenses),
                'total_net_revenue': float(total_net_revenue),
                'avg_monthly_revenue': float(avg_monthly_revenue),
                'months_with_data': months_with_data,
                'bonus_months': bonus_months,
                'metrics_by_month': [m.to_dict() for m in metrics_list]
            }

            return summary

        except Exception as e:
            logger.error(f"Error getting metrics summary: {str(e)}")
            return {
                'year': year or date.today().year,
                'error': str(e)
            }

    @staticmethod
    def get_metrics_for_period(tenant_id, year, month):
        """
        Get metrics for a specific period.

        Args:
            tenant_id: Tenant ID
            year: Year
            month: Month

        Returns:
            MonthlyFinancialMetrics object or None
        """
        return MonthlyFinancialMetrics.query.filter_by(
            tenant_id=tenant_id,
            year=year,
            month=month
        ).first()

    @staticmethod
    def delete_metrics(metrics_id):
        """
        Delete metrics record.

        Args:
            metrics_id: MonthlyFinancialMetrics ID

        Returns:
            True if successful
        """
        try:
            metrics = MonthlyFinancialMetrics.query.get(metrics_id)
            if not metrics:
                raise ValueError(f"Metrics {metrics_id} not found")

            # Check if bonuses were already calculated
            if metrics.bonus_calculation_triggered:
                raise ValueError(
                    "Cannot delete metrics after bonuses have been calculated. "
                    "Delete bonuses first."
                )

            period = metrics.period_label
            db.session.delete(metrics)
            db.session.commit()

            logger.info(f"Deleted metrics for {period}")
            return True

        except Exception as e:
            logger.error(f"Error deleting metrics: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def get_recent_months_status(tenant_id, months_back=6):
        """
        Get status of recent months for dashboard overview.

        Args:
            tenant_id: Tenant ID
            months_back: Number of months to look back

        Returns:
            List of dicts with month status
        """
        from dateutil.relativedelta import relativedelta

        today = date.today()
        result = []

        for i in range(months_back):
            check_date = today - relativedelta(months=i)
            year = check_date.year
            month = check_date.month

            metrics = FinancialMetricsService.get_metrics_for_period(tenant_id, year, month)

            status = {
                'year': year,
                'month': month,
                'period_label': check_date.strftime('%B %Y'),
                'period_short': check_date.strftime('%b %Y'),
                'has_data': False,
                'revenue': 0,
                'net_revenue': 0,
                'data_source': None,
                'is_finalized': False,
                'bonus_calculated': False
            }

            if metrics:
                status.update({
                    'has_data': True,
                    'revenue': float(metrics.total_revenue or 0),
                    'net_revenue': float(metrics.net_revenue or 0),
                    'data_source': metrics.data_source,
                    'is_finalized': metrics.is_finalized,
                    'bonus_calculated': metrics.bonus_calculation_triggered,
                    'metrics_id': metrics.id
                })

            result.append(status)

        return result
