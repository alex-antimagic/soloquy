"""
Monthly Bonus Calculation Cron Job
Runs automatically on the 1st of each month to calculate bonuses based on previous month's performance

Schedule: 0 2 1 * * (2 AM on 1st of each month)
"""
import sys
import os
from datetime import datetime, timedelta, date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app, db
from app.models.tenant import Tenant
from app.models.bonus_rule import BonusRule
from app.services.bonus_calculation_service import BonusCalculationService
from app.services.email_service import EmailService
import logging

logger = logging.getLogger(__name__)


def send_bonus_calculation_notification(tenant, result):
    """
    Send notification to HR admins about bonus calculation results.

    Args:
        tenant: Tenant object
        result: Bonus calculation result dict
    """
    try:
        # Get HR admins
        admins = tenant.get_members(role='admin')
        owners = tenant.get_members(role='owner')
        recipients = list(set(admins + owners))  # Remove duplicates

        if not recipients:
            logger.warning(f"No admins found for tenant {tenant.id} to send bonus notification")
            return

        email_service = EmailService()

        for admin in recipients:
            try:
                # Generate email content
                subject = f"Monthly Bonuses Calculated - {result.get('period_label', 'Latest Period')}"

                # Build email body
                body = f"""
                <h2>Monthly Bonus Calculation Complete</h2>

                <p>Hello {admin.first_name or 'Admin'},</p>

                <p>The monthly bonus calculation has been completed for <strong>{tenant.name}</strong>.</p>

                <h3>Summary</h3>
                <ul>
                    <li><strong>Period:</strong> {result.get('period_label', 'N/A')}</li>
                    <li><strong>Bonuses Created:</strong> {result.get('bonuses_created', 0)}</li>
                    <li><strong>Total Amount:</strong> ${result.get('total_amount', 0):,.2f}</li>
                    <li><strong>Eligible Employees:</strong> {len(result.get('employees', []))}</li>
                </ul>

                <h3>Next Steps</h3>
                <p>Please review and approve the pending bonus compensation changes in the HR system.</p>

                <p>
                    <a href="{os.environ.get('APP_URL', 'http://localhost:5000')}/hr/compensation"
                       style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Review Bonuses
                    </a>
                </p>

                <p>Thank you!</p>
                """

                email_service.send_email(
                    to_email=admin.email,
                    subject=subject,
                    body=body
                )

                logger.info(f"Sent bonus notification to {admin.email}")

            except Exception as e:
                logger.error(f"Error sending notification to {admin.email}: {str(e)}")

    except Exception as e:
        logger.error(f"Error in send_bonus_calculation_notification: {str(e)}")


def send_missing_data_alert(tenant, year, month):
    """
    Alert admins that financial data is missing for bonus calculation.

    Args:
        tenant: Tenant object
        year: Year
        month: Month
    """
    try:
        # Get admins
        admins = tenant.get_members(role='admin')
        owners = tenant.get_members(role='owner')
        recipients = list(set(admins + owners))

        if not recipients:
            return

        email_service = EmailService()
        period_label = date(year, month, 1).strftime('%B %Y')

        for admin in recipients:
            try:
                subject = f"Action Required: Missing Financial Data for {period_label}"

                body = f"""
                <h2>Missing Financial Data</h2>

                <p>Hello {admin.first_name or 'Admin'},</p>

                <p>The monthly bonus calculation was scheduled to run for <strong>{period_label}</strong>,
                but no financial data is available for this period.</p>

                <h3>Action Required</h3>
                <p>Please either:</p>
                <ul>
                    <li>Sync financial data from QuickBooks, or</li>
                    <li>Manually enter revenue and expense data for {period_label}</li>
                </ul>

                <p>Once data is available, you can manually trigger the bonus calculation.</p>

                <p>
                    <a href="{os.environ.get('APP_URL', 'http://localhost:5000')}/hr/bonuses/financial-metrics"
                       style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Enter Financial Data
                    </a>
                </p>

                <p>Thank you!</p>
                """

                email_service.send_email(
                    to_email=admin.email,
                    subject=subject,
                    body=body
                )

            except Exception as e:
                logger.error(f"Error sending alert to {admin.email}: {str(e)}")

    except Exception as e:
        logger.error(f"Error in send_missing_data_alert: {str(e)}")


def run_monthly_bonus_calculation():
    """
    Main function to run monthly bonus calculation for all tenants.

    Runs on 1st of month for previous month's performance.
    """
    app = create_app()

    with app.app_context():
        logger.info("=" * 80)
        logger.info("MONTHLY BONUS CALCULATION JOB STARTED")
        logger.info("=" * 80)

        # Calculate for previous month
        today = datetime.utcnow()
        last_month = today.replace(day=1) - timedelta(days=1)
        year = last_month.year
        month = last_month.month

        logger.info(f"Calculating bonuses for {last_month.strftime('%B %Y')}")

        # Get all tenants with active bonus rules
        tenants = Tenant.query.join(BonusRule).filter(
            BonusRule.is_active == True,
            Tenant.is_active == True
        ).distinct().all()

        logger.info(f"Found {len(tenants)} tenants with active bonus rules")

        total_bonuses_created = 0
        total_amount = 0.0
        successful_tenants = 0
        failed_tenants = 0

        for tenant in tenants:
            try:
                logger.info(f"\nProcessing tenant: {tenant.name} (ID: {tenant.id})")

                service = BonusCalculationService()
                result = service.calculate_monthly_bonuses(
                    tenant_id=tenant.id,
                    year=year,
                    month=month,
                    triggered_by='auto_cron'
                )

                if result['success']:
                    bonuses_created = result.get('bonuses_created', 0)
                    amount = float(result.get('total_amount', 0))

                    logger.info(f"  ✓ Success: {bonuses_created} bonuses, ${amount:,.2f}")

                    total_bonuses_created += bonuses_created
                    total_amount += amount
                    successful_tenants += 1

                    # Send notification to admins
                    if bonuses_created > 0:
                        result['period_label'] = last_month.strftime('%B %Y')
                        send_bonus_calculation_notification(tenant, result)
                    else:
                        logger.info("  ℹ No bonuses created (rules not met or no eligible employees)")

                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.warning(f"  ⚠ Failed: {error_msg}")
                    failed_tenants += 1

                    # If failed due to missing data, alert admins
                    if 'no data' in error_msg.lower() or 'metrics' in error_msg.lower():
                        send_missing_data_alert(tenant, year, month)

            except Exception as e:
                logger.error(f"  ✗ Error processing tenant {tenant.id}: {str(e)}")
                failed_tenants += 1

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("MONTHLY BONUS CALCULATION JOB COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Tenants Processed: {len(tenants)}")
        logger.info(f"  ✓ Successful: {successful_tenants}")
        logger.info(f"  ✗ Failed: {failed_tenants}")
        logger.info(f"Total Bonuses Created: {total_bonuses_created}")
        logger.info(f"Total Amount: ${total_amount:,.2f}")
        logger.info("=" * 80)


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        run_monthly_bonus_calculation()
    except Exception as e:
        logger.error(f"Fatal error in monthly bonus job: {str(e)}")
        sys.exit(1)
