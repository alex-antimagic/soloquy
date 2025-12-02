"""
Tests for department and agent management
"""
import pytest
from app.models.department import Department
from app.models.agent import Agent
from app.models.tenant import TenantMembership
from app.models.message import Message


class TestDepartmentTenantIsolation:
    """Test suite for department tenant isolation"""

    def test_cannot_access_other_tenant_department(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot access departments from other tenants"""
        # Create department in tenant_2
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
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

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_update_other_tenant_department(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot update departments from other tenants"""
        # Create department in tenant_2
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to update department from tenant_2
        response = client.post(
            f'/department/{dept_2.id}/update',
            data={'name': 'Hacked Name'}
        )

        # Should be denied
        assert response.status_code in [403, 404]

        # Verify department wasn't updated
        dept_check = Department.query.get(dept_2.id)
        assert dept_check.name == 'Other Department'

    def test_cannot_delete_other_tenant_department(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot delete departments from other tenants"""
        # Create department in tenant_2
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.commit()
        dept_2_id = dept_2.id

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to delete department from tenant_2
        response = client.post(f'/department/{dept_2_id}/delete')

        # Should be denied
        assert response.status_code in [403, 404]

        # Verify department still exists
        dept_check = Department.query.get(dept_2_id)
        assert dept_check is not None

    def test_department_list_filtered_by_tenant(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that department listings are filtered by tenant"""
        # Create departments in both tenants
        dept_1 = Department(
            name='My Department',
            slug='my-dept',
            tenant_id=test_tenant.id,
            color='#0000FF'
        )
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add_all([dept_1, dept_2])
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Get department list
        response = client.get('/tenant/agents')  # Departments are shown on agents page

        # Should show only test_tenant departments
        assert response.status_code == 200
        assert b'My Department' in response.data
        assert b'Other Department' not in response.data


class TestAgentTenantIsolation:
    """Test suite for agent tenant isolation"""

    def test_cannot_access_other_tenant_agent(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot chat with agents from other tenants"""
        # Create department and agent in tenant_2
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.flush()

        agent_2 = Agent(
            name='Other Agent',
            department_id=dept_2.id,
            created_by_id=test_user.id,
            system_prompt='Test'
        )
        db_session.add(agent_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access agent from tenant_2
        response = client.get(f'/chat/agent/{agent_2.id}')

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_send_message_to_other_tenant_agent(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot send messages to agents from other tenants"""
        # Create department and agent in tenant_2
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.flush()

        agent_2 = Agent(
            name='Other Agent',
            department_id=dept_2.id,
            created_by_id=test_user.id,
            system_prompt='Test'
        )
        db_session.add(agent_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to send message to agent from tenant_2
        response = client.post(
            f'/chat/agent/{agent_2.id}/send',
            json={'content': 'Hello'},
            headers={'Content-Type': 'application/json'}
        )

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_update_other_tenant_agent(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot update agents from other tenants"""
        # Create department and agent in tenant_2
        dept_2 = Department(
            name='Other Department',
            slug='other-dept',
            tenant_id=test_tenant_2.id,
            color='#FF0000'
        )
        db_session.add(dept_2)
        db_session.flush()

        agent_2 = Agent(
            name='Other Agent',
            department_id=dept_2.id,
            created_by_id=test_user.id,
            system_prompt='Original'
        )
        db_session.add(agent_2)
        db_session.commit()

        # Login as test_user (belongs to test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to update agent from tenant_2
        response = client.post(
            f'/tenant/agents/{agent_2.id}/update',
            data={'name': 'Hacked Name', 'system_prompt': 'Hacked'}
        )

        # Should be denied
        assert response.status_code in [403, 404]

        # Verify agent wasn't updated
        agent_check = Agent.query.get(agent_2.id)
        assert agent_check.name == 'Other Agent'
        assert agent_check.system_prompt == 'Original'


class TestDepartmentWorkflows:
    """Test suite for department management workflows"""

    def test_create_department(self, client, test_user, test_tenant, db_session):
        """Test creating a new department"""
        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create department
        response = client.post('/department/create', data={
            'name': 'Sales',
            'description': 'Sales department',
            'color': '#00FF00'
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify department was created
        dept = Department.query.filter_by(name='Sales', tenant_id=test_tenant.id).first()
        assert dept is not None
        assert dept.tenant_id == test_tenant.id
        assert dept.color == '#00FF00'

    def test_update_department(self, client, test_user, test_tenant, test_department, db_session):
        """Test updating a department"""
        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Update department
        response = client.post(
            f'/department/{test_department.id}/update',
            data={'name': 'Updated Name', 'description': 'Updated description'}
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify update
        dept_check = Department.query.get(test_department.id)
        assert dept_check.name == 'Updated Name'
        assert dept_check.description == 'Updated description'


class TestAgentWorkflows:
    """Test suite for agent management workflows"""

    def test_create_agent(self, client, test_user, test_tenant, test_department, db_session):
        """Test creating a new agent"""
        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create agent
        response = client.post('/tenant/agents/create', data={
            'name': 'Sales Bot',
            'department_id': test_department.id,
            'system_prompt': 'You are a helpful sales assistant',
            'model': 'claude-sonnet-4-5-20250929'
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify agent was created
        agent = Agent.query.filter_by(name='Sales Bot').first()
        assert agent is not None
        assert agent.department_id == test_department.id
        assert agent.created_by_id == test_user.id

    def test_update_agent_system_prompt(self, client, test_user, test_tenant, test_department, db_session):
        """Test updating an agent's system prompt"""
        # Create agent
        agent = Agent(
            name='Test Agent',
            department_id=test_department.id,
            created_by_id=test_user.id,
            system_prompt='Original prompt'
        )
        db_session.add(agent)
        db_session.commit()

        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Update agent
        response = client.post(
            f'/tenant/agents/{agent.id}/update',
            data={
                'name': 'Test Agent',
                'system_prompt': 'Updated prompt',
                'department_id': test_department.id
            }
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify update
        agent_check = Agent.query.get(agent.id)
        assert agent_check.system_prompt == 'Updated prompt'

    def test_agent_access_control_all_users(self, client, test_user, test_user_2, test_tenant, test_department, db_session):
        """Test agent access control with 'all' setting"""
        # Add test_user_2 to tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create agent with 'all' access
        agent = Agent(
            name='Public Agent',
            department_id=test_department.id,
            created_by_id=test_user.id,
            system_prompt='Test',
            access_control='all'
        )
        db_session.add(agent)
        db_session.commit()

        # Login as test_user_2 (regular member)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user_2.id
            sess['current_tenant_id'] = test_tenant.id

        # Should be able to access agent
        response = client.get(f'/chat/agent/{agent.id}')
        assert response.status_code == 200

    def test_agent_access_control_role_based(self, client, test_user, test_user_2, test_tenant, test_department, db_session):
        """Test agent access control with role-based restrictions"""
        # Add test_user_2 to tenant as regular member
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create agent with role-based access (only owners/admins)
        agent = Agent(
            name='Admin Agent',
            department_id=test_department.id,
            created_by_id=test_user.id,
            system_prompt='Test',
            access_control='role',
            allowed_roles='["owner", "admin"]'
        )
        db_session.add(agent)
        db_session.commit()

        # Login as test_user_2 (regular member - not owner/admin)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user_2.id
            sess['current_tenant_id'] = test_tenant.id

        # Should be denied access
        response = client.get(f'/chat/agent/{agent.id}')
        assert response.status_code in [403, 404]

    def test_agent_integration_permissions(self, client, test_user, test_tenant, test_department, db_session):
        """Test setting agent integration permissions"""
        # Create agent
        agent = Agent(
            name='Integration Agent',
            department_id=test_department.id,
            created_by_id=test_user.id,
            system_prompt='Test',
            enable_quickbooks=False
        )
        db_session.add(agent)
        db_session.commit()

        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Enable QuickBooks integration
        response = client.post(
            f'/tenant/agents/{agent.id}/update',
            data={
                'name': 'Integration Agent',
                'department_id': test_department.id,
                'system_prompt': 'Test',
                'enable_quickbooks': 'on'  # Checkbox sends 'on'
            }
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify permission was set
        agent_check = Agent.query.get(agent.id)
        assert agent_check.enable_quickbooks == True

    def test_delete_department_with_agents(self, client, test_user, test_tenant, test_department, db_session):
        """Test deleting a department that has agents"""
        # Create agent in department
        agent = Agent(
            name='Test Agent',
            department_id=test_department.id,
            created_by_id=test_user.id,
            system_prompt='Test'
        )
        db_session.add(agent)
        db_session.commit()

        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to delete department
        response = client.post(f'/department/{test_department.id}/delete')

        # Behavior depends on implementation:
        # - Either prevents deletion (with error message)
        # - Or cascades deletion to agents
        # Both are valid, so we just check it doesn't return 500
        assert response.status_code in [200, 302, 400, 403]
