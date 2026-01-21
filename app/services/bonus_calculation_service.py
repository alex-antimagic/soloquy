"""
Bonus Calculation Service
Handles automatic bonus calculation based on KPI rules and financial metrics
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from app import db
from app.models.monthly_financial_metrics import MonthlyFinancialMetrics
from app.models.bonus_rule import BonusRule
from app.models.bonus_calculation_log import BonusCalculationLog
from app.models.compensation_change import CompensationChange
from app.models.employee import Employee
import logging

logger = logging.getLogger(__name__)


class BonusCalculationService:
    """Service for calculating and creating KPI-based bonuses"""

    @staticmethod
    def calculate_monthly_bonuses(tenant_id, year, month, triggered_by='manual_admin',
                                  triggered_by_user_id=None):
        """
        Main entry point for bonus calculation.

        Args:
            tenant_id: Tenant ID
            year: Year (e.g., 2024)
            month: Month (1-12)
            triggered_by: How calculation was triggered ('auto_cron', 'manual_admin')
            triggered_by_user_id: User ID if triggered manually

        Returns:
            Dict with results: {
                'success': bool,
                'bonuses_created': int,
                'total_amount': Decimal,
                'calculation_log_id': int,
                'employees': list,
                'error': str (if failed)
            }
        """
        try:
            # Check for duplicate bonus calculation
            if BonusCalculationService.prevent_duplicate_bonuses(tenant_id, year, month):
                return {
                    'success': False,
                    'error': 'Bonuses already calculated for this period',
                    'bonuses_created': 0,
                    'total_amount': 0
                }

            # Get or create monthly metrics
            metrics, created = BonusCalculationService.get_or_create_monthly_metrics(
                tenant_id, year, month
            )

            if not metrics:
                return {
                    'success': False,
                    'error': 'Failed to retrieve financial metrics',
                    'bonuses_created': 0,
                    'total_amount': 0
                }

            # If no financial data yet, try to sync from QuickBooks
            if metrics.total_revenue == 0 and metrics.data_source == 'manual':
                BonusCalculationService.sync_quickbooks_data(tenant_id, year, month)
                # Refresh metrics
                db.session.refresh(metrics)

            # Create calculation log
            calc_log = BonusCalculationLog(
                tenant_id=tenant_id,
                financial_metrics_id=metrics.id,
                triggered_by=triggered_by,
                triggered_by_user_id=triggered_by_user_id
            )
            db.session.add(calc_log)
            db.session.flush()  # Get ID for linking

            # Evaluate bonus rules
            passed_rules = BonusCalculationService.evaluate_bonus_rules(tenant_id, metrics)

            calc_log.rules_evaluated = BonusRule.query.filter_by(
                tenant_id=tenant_id,
                is_active=True
            ).count()
            calc_log.rules_passed = len(passed_rules)

            if not passed_rules:
                calc_log.status = 'no_rules'
                db.session.commit()
                return {
                    'success': True,
                    'bonuses_created': 0,
                    'total_amount': 0,
                    'calculation_log_id': calc_log.id,
                    'message': 'No bonus rules passed'
                }

            # Calculate bonuses for each passed rule
            all_employees = []
            total_bonuses_created = 0
            total_amount = Decimal('0.00')

            # Set effective date to 1st of next month (bonuses for Jan paid on Feb 1)
            if month == 12:
                as_of_date = date(year + 1, 1, 1)
            else:
                as_of_date = date(year, month + 1, 1)

            for rule in passed_rules:
                # Log passed rule
                config = rule.get_rule_config()
                calc_log.add_passed_rule(
                    rule.id,
                    rule.rule_name,
                    metrics.net_revenue,  # Could vary based on rule metric
                    config.get('threshold', 0)
                )

                # Get eligible employees
                eligible_employees = BonusCalculationService.get_eligible_employees(
                    tenant_id, rule, as_of_date
                )

                # Create bonus records
                created = BonusCalculationService.create_bonus_compensation_changes(
                    eligible_employees, rule, metrics, calc_log, as_of_date
                )

                total_bonuses_created += created['count']
                total_amount += created['total_amount']
                all_employees.extend(created['employees'])

            # Update calculation log with results
            calc_log.employees_eligible = len(all_employees)
            calc_log.bonuses_created = total_bonuses_created
            calc_log.total_bonus_amount = total_amount
            calc_log.status = 'completed'

            # Mark metrics as having triggered bonus calculation
            metrics.bonus_calculation_triggered = True

            db.session.commit()

            logger.info(f"Bonus calculation complete: {total_bonuses_created} bonuses totaling ${total_amount}")

            return {
                'success': True,
                'bonuses_created': total_bonuses_created,
                'total_amount': total_amount,
                'calculation_log_id': calc_log.id,
                'employees': all_employees
            }

        except Exception as e:
            logger.error(f"Error in bonus calculation: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'bonuses_created': 0,
                'total_amount': 0
            }

    @staticmethod
    def get_or_create_monthly_metrics(tenant_id, year, month):
        """
        Get existing metrics or create new record.

        Returns:
            Tuple of (metrics, created)
        """
        return MonthlyFinancialMetrics.get_or_create(tenant_id, year, month)

    @staticmethod
    def sync_quickbooks_data(tenant_id, year, month):
        """
        Fetch P&L data from QuickBooks for the month.

        Args:
            tenant_id: Tenant ID
            year: Year
            month: Month

        Returns:
            True if successful, False otherwise
        """
        try:
            from app.services.quickbooks_service import QuickBooksService
            from app.models.integration import Integration

            # Check if QuickBooks integration exists
            integration = Integration.query.filter_by(
                tenant_id=tenant_id,
                service_name='quickbooks',
                is_active=True
            ).first()

            if not integration:
                logger.info(f"No active QuickBooks integration for tenant {tenant_id}")
                return False

            # Calculate date range for the month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)

            # Fetch P&L data
            qb_service = QuickBooksService()
            pl_data = qb_service.get_profit_loss(integration, start_date, end_date)

            if not pl_data:
                logger.warning(f"No P&L data returned from QuickBooks")
                return False

            # Update metrics
            metrics, created = MonthlyFinancialMetrics.get_or_create(tenant_id, year, month)
            metrics.total_revenue = pl_data.get('total_revenue', 0)
            metrics.total_expenses = pl_data.get('total_expenses', 0)
            metrics.net_revenue = pl_data.get('net_income', 0)
            metrics.gross_profit = pl_data.get('gross_profit', pl_data.get('net_income', 0))
            metrics.data_source = 'quickbooks'
            metrics.quickbooks_synced_at = datetime.utcnow()

            db.session.commit()
            logger.info(f"Synced QuickBooks data for {year}-{month:02d}")
            return True

        except Exception as e:
            logger.error(f"Error syncing QuickBooks data: {str(e)}")
            return False

    @staticmethod
    def evaluate_bonus_rules(tenant_id, metrics):
        """
        Evaluate all active rules against metrics.

        Args:
            tenant_id: Tenant ID
            metrics: MonthlyFinancialMetrics object

        Returns:
            List of BonusRule objects that passed
        """
        passed_rules = []

        # Get all active rules for this tenant
        rules = BonusRule.query.filter_by(
            tenant_id=tenant_id,
            is_active=True
        ).all()

        for rule in rules:
            # Check if rule is effective
            check_date = date(metrics.year, metrics.month, 1)
            if not rule.is_effective_on(check_date):
                continue

            # Get the metric to evaluate
            config = rule.get_rule_config()
            metric_name = config.get('metric', 'net_revenue')

            # Map metric name to actual value
            metric_value = getattr(metrics, metric_name, 0)

            # Evaluate the rule
            if rule.evaluate_metric(metric_value):
                passed_rules.append(rule)
                logger.info(f"Rule '{rule.rule_name}' passed: {metric_name}=${metric_value}")

        return passed_rules

    @staticmethod
    def get_eligible_employees(tenant_id, rule, as_of_date):
        """
        Filter employees based on rule eligibility criteria.

        Args:
            tenant_id: Tenant ID
            rule: BonusRule object
            as_of_date: Date to check eligibility

        Returns:
            List of eligible Employee objects
        """
        # Start with active employees
        query = Employee.query.filter_by(
            tenant_id=tenant_id,
            status='active'
        )

        # Filter by tenure
        if rule.minimum_tenure_days > 0:
            cutoff_date = as_of_date - timedelta(days=rule.minimum_tenure_days)
            query = query.filter(Employee.hire_date <= cutoff_date)

        # Filter by department
        if not rule.applies_to_all_employees:
            eligible_depts = rule.get_eligible_departments()
            if eligible_depts:
                query = query.filter(Employee.department_name.in_(eligible_depts))

        # Filter employees with bonus target percentage
        if rule.use_employee_target_percentage:
            query = query.filter(Employee.bonus_target_percentage > 0)

        employees = query.all()
        logger.info(f"Found {len(employees)} eligible employees for rule '{rule.rule_name}'")

        return employees

    @staticmethod
    def calculate_bonus_amount(employee, rule):
        """
        Calculate bonus amount for an employee.

        Args:
            employee: Employee object
            rule: BonusRule object

        Returns:
            Decimal bonus amount
        """
        if rule.use_employee_target_percentage:
            if not employee.salary or not employee.bonus_target_percentage:
                return Decimal('0.00')

            bonus = Decimal(str(employee.salary)) * (
                Decimal(str(employee.bonus_target_percentage)) / Decimal('100')
            )
            return bonus.quantize(Decimal('0.01'))
        elif rule.fixed_bonus_amount:
            return Decimal(str(rule.fixed_bonus_amount))
        else:
            return Decimal('0.00')

    @staticmethod
    def create_bonus_compensation_changes(employees, rule, metrics, calc_log, effective_date):
        """
        Create pending CompensationChange records for bonuses.

        Args:
            employees: List of eligible Employee objects
            rule: BonusRule object
            metrics: MonthlyFinancialMetrics object
            calc_log: BonusCalculationLog object
            effective_date: Date for the bonus

        Returns:
            Dict with results: {
                'count': int,
                'total_amount': Decimal,
                'employees': list
            }
        """
        result = {
            'count': 0,
            'total_amount': Decimal('0.00'),
            'employees': []
        }

        for employee in employees:
            try:
                bonus_amount = BonusCalculationService.calculate_bonus_amount(employee, rule)

                if bonus_amount <= 0:
                    continue

                # Create compensation change record
                comp_change = CompensationChange(
                    tenant_id=employee.tenant_id,
                    employee_id=employee.id,
                    change_type='bonus',
                    effective_date=effective_date,
                    bonus_amount=bonus_amount,
                    bonus_currency='USD',
                    bonus_type=rule.bonus_type,
                    reason=f"KPI Bonus: {rule.rule_name} ({metrics.period_label})",
                    notes=f"Auto-generated bonus based on {metrics.period_label} financial performance. "
                          f"Net revenue: ${metrics.net_revenue}",
                    status='planned',  # Requires approval
                    kpi_rule_id=rule.id,
                    calculation_log_id=calc_log.id,
                    financial_metrics_id=metrics.id
                )

                db.session.add(comp_change)

                # Log eligible employee
                calc_log.add_eligible_employee(
                    employee.id,
                    employee.full_name,
                    bonus_amount
                )

                result['count'] += 1
                result['total_amount'] += bonus_amount
                result['employees'].append({
                    'employee_id': employee.id,
                    'employee_name': employee.full_name,
                    'bonus_amount': float(bonus_amount)
                })

                logger.info(f"Created bonus for {employee.full_name}: ${bonus_amount}")

            except Exception as e:
                error_msg = f"Error creating bonus for employee {employee.id}: {str(e)}"
                logger.error(error_msg)
                calc_log.add_error(error_msg)

        return result

    @staticmethod
    def prevent_duplicate_bonuses(tenant_id, year, month):
        """
        Check if bonuses already calculated for this period.

        Args:
            tenant_id: Tenant ID
            year: Year
            month: Month

        Returns:
            True if bonuses already calculated, False otherwise
        """
        metrics = MonthlyFinancialMetrics.query.filter_by(
            tenant_id=tenant_id,
            year=year,
            month=month
        ).first()

        if metrics and metrics.bonus_calculation_triggered:
            logger.warning(f"Bonuses already calculated for {year}-{month:02d}")
            return True

        return False
