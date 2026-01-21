"""
Employee Sync Service
Handles automatic synchronization between User and Employee records
"""
from datetime import datetime, date
from app import db
from app.models.employee import Employee
from app.models.user import User
from app.models.tenant import TenantMembership
import logging

logger = logging.getLogger(__name__)


class EmployeeSyncService:
    """Service for syncing user data to employee records"""

    @staticmethod
    def create_employee_from_user(user_id: int, tenant_id: int, joined_at: datetime = None) -> Employee:
        """
        Auto-create employee record when user joins workspace.

        Args:
            user_id: User ID to create employee for
            tenant_id: Tenant ID for the employee
            joined_at: When user joined (defaults to now)

        Returns:
            Created Employee object

        Raises:
            ValueError: If user not found or employee already exists
        """
        # Check if employee already exists (prevent duplicates)
        existing_employee = Employee.query.filter_by(
            tenant_id=tenant_id,
            user_id=user_id
        ).first()

        if existing_employee:
            # Reactivate if terminated
            if existing_employee.status == 'terminated':
                logger.info(f"Reactivating terminated employee {existing_employee.id} for user {user_id}")
                return EmployeeSyncService.reactivate_employee(existing_employee.id)
            logger.info(f"Employee already exists for user {user_id} in tenant {tenant_id}")
            return existing_employee

        # Get user
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Generate employee number
        employee_number = Employee.generate_employee_number(tenant_id)

        # Create employee with synced user fields
        employee = Employee(
            tenant_id=tenant_id,
            user_id=user_id,
            employee_number=employee_number,
            first_name=user.first_name or '',
            last_name=user.last_name or '',
            email=user.email,
            hire_date=joined_at.date() if joined_at else date.today(),
            status='active'
        )

        db.session.add(employee)
        db.session.commit()

        logger.info(f"Created employee {employee.employee_number} for user {user_id} in tenant {tenant_id}")
        return employee

    @staticmethod
    def sync_user_to_employee(employee_id: int) -> bool:
        """
        Update employee when user profile changes.

        Args:
            employee_id: Employee ID to sync

        Returns:
            True if successful, False otherwise
        """
        try:
            employee = Employee.query.get(employee_id)
            if not employee:
                logger.warning(f"Employee {employee_id} not found")
                return False

            if not employee.user:
                logger.warning(f"Employee {employee_id} has no linked user")
                return False

            # Call the model's sync method
            employee.sync_from_user()
            db.session.commit()

            logger.info(f"Synced employee {employee_id} from user {employee.user_id}")
            return True

        except Exception as e:
            logger.error(f"Error syncing employee {employee_id}: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def handle_membership_removal(employee_id: int) -> bool:
        """
        Mark employee as terminated when removed from workspace.

        Args:
            employee_id: Employee ID to terminate

        Returns:
            True if successful, False otherwise
        """
        try:
            employee = Employee.query.get(employee_id)
            if not employee:
                logger.warning(f"Employee {employee_id} not found")
                return False

            # Set termination status
            employee.status = 'terminated'
            employee.termination_date = date.today()

            # Add HR note
            employee.add_hr_note(
                note_type='general',
                note='Employee removed from workspace membership',
                created_by='System',
                is_confidential=False
            )

            db.session.commit()

            logger.info(f"Terminated employee {employee_id}")
            return True

        except Exception as e:
            logger.error(f"Error terminating employee {employee_id}: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def reactivate_employee(employee_id: int) -> Employee:
        """
        Reactivate terminated employee if user rejoins workspace.

        Args:
            employee_id: Employee ID to reactivate

        Returns:
            Reactivated Employee object
        """
        try:
            employee = Employee.query.get(employee_id)
            if not employee:
                raise ValueError(f"Employee {employee_id} not found")

            # Set active status
            employee.status = 'active'
            employee.termination_date = None

            # Add HR note
            employee.add_hr_note(
                note_type='general',
                note='Employee reactivated - rejoined workspace',
                created_by='System',
                is_confidential=False
            )

            db.session.commit()

            logger.info(f"Reactivated employee {employee_id}")
            return employee

        except Exception as e:
            logger.error(f"Error reactivating employee {employee_id}: {str(e)}")
            db.session.rollback()
            raise

    @staticmethod
    def backfill_existing_users(tenant_id: int = None) -> dict:
        """
        Migration utility: Create employees for existing workspace members.

        Args:
            tenant_id: Optional tenant ID to backfill (if None, backfills all tenants)

        Returns:
            Dict with results: {
                'created': int,
                'skipped': int,
                'reactivated': int,
                'errors': list
            }
        """
        results = {
            'created': 0,
            'skipped': 0,
            'reactivated': 0,
            'errors': []
        }

        try:
            # Build query for active memberships
            query = TenantMembership.query.filter_by(is_active=True)
            if tenant_id:
                query = query.filter_by(tenant_id=tenant_id)

            memberships = query.all()

            logger.info(f"Starting backfill for {len(memberships)} memberships")

            for membership in memberships:
                try:
                    # Check if employee already exists
                    existing_employee = Employee.query.filter_by(
                        tenant_id=membership.tenant_id,
                        user_id=membership.user_id
                    ).first()

                    if existing_employee:
                        if existing_employee.status == 'terminated':
                            # Reactivate
                            EmployeeSyncService.reactivate_employee(existing_employee.id)
                            results['reactivated'] += 1
                        else:
                            # Already active
                            results['skipped'] += 1
                    else:
                        # Create new employee
                        EmployeeSyncService.create_employee_from_user(
                            user_id=membership.user_id,
                            tenant_id=membership.tenant_id,
                            joined_at=membership.joined_at
                        )
                        results['created'] += 1

                except Exception as e:
                    error_msg = f"Error processing user {membership.user_id} in tenant {membership.tenant_id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)

            logger.info(f"Backfill complete: {results}")
            return results

        except Exception as e:
            logger.error(f"Error in backfill_existing_users: {str(e)}")
            results['errors'].append(str(e))
            return results

    @staticmethod
    def sync_all_employees_for_user(user_id: int) -> dict:
        """
        Sync all employee records for a user across all tenants.
        Called when user profile is updated.

        Args:
            user_id: User ID to sync

        Returns:
            Dict with results: {
                'synced': int,
                'errors': list
            }
        """
        results = {
            'synced': 0,
            'errors': []
        }

        try:
            employees = Employee.query.filter_by(user_id=user_id).all()

            for employee in employees:
                try:
                    if EmployeeSyncService.sync_user_to_employee(employee.id):
                        results['synced'] += 1
                except Exception as e:
                    error_msg = f"Error syncing employee {employee.id}: {str(e)}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)

            return results

        except Exception as e:
            logger.error(f"Error in sync_all_employees_for_user: {str(e)}")
            results['errors'].append(str(e))
            return results
