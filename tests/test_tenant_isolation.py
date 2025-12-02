"""
Tests for tenant isolation security
Ensures users cannot access resources from other tenants
"""
import pytest
from flask import g
from app.models.task import Task
from app.models.department import Department
from app.models.agent import Agent


class TestTenantIsolation:
    """Test suite for tenant isolation vulnerabilities"""

    def test_cannot_access_other_tenant_department(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot access departments from other tenants"""
        # Create department in tenant 2
        dept_2 = Department(
            name='Other Department',
            slug='other-department',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access department from tenant_2
        response = client.get(f'/department/{dept_2.id}')

        # Should be denied (either 403, 404, or 302 redirect)
        assert response.status_code in [302, 403, 404]

    def test_cannot_access_other_tenant_tasks(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot access tasks from other tenants"""
        # Create task in tenant 2
        task_2 = Task(
            title='Other Task',
            tenant_id=test_tenant_2.id,
            created_by_id=test_user.id  # Created by same user but in different tenant
        )
        db_session.add(task_2)
        db_session.commit()

        # Login as test_user in test_tenant
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access task from tenant_2
        response = client.get(f'/tasks/{task_2.id}')

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_delete_other_tenant_department(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot delete departments from other tenants"""
        # Create department in tenant 2
        dept_2 = Department(
            name='Other Department',
            slug='other-department',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.commit()
        dept_2_id = dept_2.id

        # Login as test_user (owner of test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to delete department from tenant_2
        response = client.post(f'/department/{dept_2_id}/delete')

        # Should be denied (either 302 redirect, 403, or 404)
        assert response.status_code in [302, 403, 404]

        # Verify department still exists
        dept_check = Department.query.get(dept_2_id)
        assert dept_check is not None

    def test_crm_deal_stage_isolation(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot move deals to stages from other tenants"""
        # This test would require CRM models to be set up
        # TODO: Implement when CRM models are available in test fixtures
        pytest.skip("CRM fixtures not yet implemented")

    def test_department_member_isolation(self, client, test_user, test_user_2, test_tenant, test_department, db_session):
        """Test that users cannot add members from other tenants to departments"""
        # Login as test_user (owner of test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to add test_user_2 (who is NOT in test_tenant) to department
        response = client.post(
            f'/department/{test_department.id}/members/add',
            data={'user_id': test_user_2.id}
        )

        # Should be rejected (user not in workspace)
        assert response.status_code in [302, 404]  # Redirect with flash or 404

        # Verify member was not added
        members = test_department.get_members()
        member_ids = [m.id for m in members]
        assert test_user_2.id not in member_ids
