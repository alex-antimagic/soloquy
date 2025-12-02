"""
Tests for task management workflows and isolation
"""
import pytest
from datetime import datetime, timedelta
from app.models.task import Task
from app.models.tenant import TenantMembership
from app.models.department import Department


class TestTaskTenantIsolation:
    """Test suite for task tenant isolation"""

    def test_cannot_access_other_tenant_task(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot access tasks from other tenants"""
        # Create task in tenant_2
        task_2 = Task(
            title='Other Task',
            tenant_id=test_tenant_2.id,
            created_by_id=test_user.id
        )
        db_session.add(task_2)
        db_session.commit()

        # Login as test_user (in test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access task from tenant_2
        response = client.get(f'/tasks/{task_2.id}')

        # Should be denied
        assert response.status_code in [403, 404]

    def test_cannot_update_other_tenant_task(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot update tasks from other tenants"""
        # Create task in tenant_2
        task_2 = Task(
            title='Other Task',
            tenant_id=test_tenant_2.id,
            created_by_id=test_user.id
        )
        db_session.add(task_2)
        db_session.commit()

        # Login as test_user (in test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to update task from tenant_2
        response = client.post(
            f'/tasks/{task_2.id}/update',
            json={'title': 'Updated Title', 'status': 'completed'}
        )

        # Should be denied
        assert response.status_code in [403, 404]

        # Verify task wasn't updated
        task_check = Task.query.get(task_2.id)
        assert task_check.title == 'Other Task'
        assert task_check.status != 'completed'

    def test_cannot_delete_other_tenant_task(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that users cannot delete tasks from other tenants"""
        # Create task in tenant_2
        task_2 = Task(
            title='Other Task',
            tenant_id=test_tenant_2.id,
            created_by_id=test_user.id
        )
        db_session.add(task_2)
        db_session.commit()
        task_2_id = task_2.id

        # Login as test_user (in test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to delete task from tenant_2
        response = client.post(f'/tasks/{task_2_id}/delete')

        # Should be denied
        assert response.status_code in [403, 404]

        # Verify task still exists
        task_check = Task.query.get(task_2_id)
        assert task_check is not None

    def test_task_list_filtered_by_tenant(self, client, test_user, test_tenant, test_tenant_2, db_session):
        """Test that task listings are filtered by tenant"""
        # Create tasks in both tenants
        task_1 = Task(
            title='My Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id
        )
        task_2 = Task(
            title='Other Task',
            tenant_id=test_tenant_2.id,
            created_by_id=test_user.id
        )
        db_session.add_all([task_1, task_2])
        db_session.commit()

        # Login as test_user (in test_tenant)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Get task list
        response = client.get('/tasks/')

        # Should show only test_tenant tasks
        assert response.status_code == 200
        assert b'My Task' in response.data
        assert b'Other Task' not in response.data


class TestTaskWorkflows:
    """Test suite for task management workflows"""

    def test_create_task(self, client, test_user, test_tenant, db_session):
        """Test creating a new task"""
        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create task
        response = client.post('/tasks/create', json={
            'title': 'New Task',
            'description': 'Task description',
            'priority': 'high',
            'due_date': (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%d')
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify task was created
        task = Task.query.filter_by(title='New Task', tenant_id=test_tenant.id).first()
        assert task is not None
        assert task.tenant_id == test_tenant.id
        assert task.created_by_id == test_user.id
        assert task.priority == 'high'

    def test_assign_task_to_user(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test assigning a task to another user"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create task
        task = Task(
            title='Assignable Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id
        )
        db_session.add(task)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Assign task to test_user_2
        response = client.post(
            f'/tasks/{task.id}/update',
            json={
                'title': 'Assignable Task',
                'assigned_to_id': test_user_2.id
            }
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify assignment
        task_check = Task.query.get(task.id)
        assert task_check.assigned_to_id == test_user_2.id

    def test_complete_task(self, client, test_user, test_tenant, db_session):
        """Test marking a task as completed"""
        # Create task
        task = Task(
            title='Task to Complete',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id,
            status='in_progress'
        )
        db_session.add(task)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Complete task
        response = client.post(
            f'/tasks/{task.id}/complete',
            follow_redirects=False
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify completion
        task_check = Task.query.get(task.id)
        assert task_check.status == 'completed'
        assert task_check.completed_at is not None

    def test_create_task_with_department(self, client, test_user, test_tenant, test_department, db_session):
        """Test creating a task associated with a department"""
        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create task with department
        response = client.post('/tasks/create', json={
            'title': 'Department Task',
            'department_id': test_department.id
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify task was created with department
        task = Task.query.filter_by(title='Department Task').first()
        assert task is not None
        assert task.department_id == test_department.id

    def test_filter_tasks_by_status(self, client, test_user, test_tenant, db_session):
        """Test filtering tasks by status"""
        # Create tasks with different statuses
        task_pending = Task(
            title='Pending Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id,
            status='pending'
        )
        task_completed = Task(
            title='Completed Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id,
            status='completed'
        )
        db_session.add_all([task_pending, task_completed])
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Filter by pending status
        response = client.get('/tasks/?status=pending')

        # Should show only pending tasks
        assert response.status_code == 200
        assert b'Pending Task' in response.data
        assert b'Completed Task' not in response.data

    def test_update_task_priority(self, client, test_user, test_tenant, db_session):
        """Test updating task priority"""
        # Create task
        task = Task(
            title='Priority Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id,
            priority='low'
        )
        db_session.add(task)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Update priority
        response = client.post(
            f'/tasks/{task.id}/update',
            json={
                'title': 'Priority Task',
                'priority': 'urgent'
            }
        )

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify priority change
        task_check = Task.query.get(task.id)
        assert task_check.priority == 'urgent'

    def test_create_subtask(self, client, test_user, test_tenant, db_session):
        """Test creating a subtask"""
        # Create parent task
        parent_task = Task(
            title='Parent Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id
        )
        db_session.add(parent_task)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Create subtask
        response = client.post('/tasks/create', json={
            'title': 'Subtask',
            'parent_task_id': parent_task.id
        }, follow_redirects=False)

        # Should be successful
        assert response.status_code in [200, 302]

        # Verify subtask was created
        subtask = Task.query.filter_by(title='Subtask').first()
        assert subtask is not None
        assert subtask.parent_task_id == parent_task.id
        assert subtask.tenant_id == test_tenant.id  # Inherits tenant

    def test_cannot_assign_task_to_user_outside_tenant(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that tasks cannot be assigned to users outside the tenant"""
        # test_user_2 is NOT in test_tenant
        # Create task in test_tenant
        task = Task(
            title='My Task',
            tenant_id=test_tenant.id,
            created_by_id=test_user.id
        )
        db_session.add(task)
        db_session.commit()

        # Login as test_user
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to assign to test_user_2 (who is not in tenant)
        response = client.post(
            f'/tasks/{task.id}/update',
            data={
                'title': 'My Task',
                'assigned_to_id': test_user_2.id
            }
        )

        # Should be rejected or ignored
        task_check = Task.query.get(task.id)
        # Assignment should either fail or be ignored
        assert task_check.assigned_to_id != test_user_2.id or response.status_code in [400, 403, 404]
