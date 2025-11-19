"""
Tests for authentication and authorization
"""
import pytest
from app.models.user import User


class TestAuthentication:
    """Test suite for user authentication"""

    def test_user_registration(self, client, db_session):
        """Test user can register with valid data"""
        response = client.post('/auth/register', data={
            'email': 'newuser@example.com',
            'full_name': 'New User',
            'password': 'SecurePass123!@#',
            'confirm_password': 'SecurePass123!@#'
        }, follow_redirects=True)

        assert response.status_code == 200

        # Verify user was created
        user = User.query.filter_by(email='newuser@example.com').first()
        assert user is not None
        assert user.full_name == 'New User'
        assert user.check_password('SecurePass123!@#')

    def test_weak_password_rejected(self, client, db_session):
        """Test that weak passwords are rejected"""
        response = client.post('/auth/register', data={
            'email': 'weak@example.com',
            'full_name': 'Weak User',
            'password': '12345',  # Too weak
            'confirm_password': '12345'
        })

        # Should show validation error
        assert b'password' in response.data.lower() or response.status_code != 302

    def test_user_login(self, client, test_user):
        """Test user can login with correct credentials"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'Test123!@#'
        }, follow_redirects=False)

        assert response.status_code == 302  # Redirect after login

    def test_user_login_wrong_password(self, client, test_user):
        """Test login fails with wrong password"""
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'WrongPassword123!@#'
        })

        # Should stay on login page with error
        assert b'email or password' in response.data.lower() or b'invalid' in response.data.lower()

    def test_account_lockout_after_failed_attempts(self, client, test_user):
        """Test account locks after multiple failed login attempts"""
        # Try to login with wrong password multiple times
        for i in range(6):  # Should lock after 5 attempts
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'WrongPassword123!@#'
            })

        # Next attempt should be locked
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'Test123!@#'  # Even correct password
        })

        assert b'locked' in response.data.lower() or b'too many' in response.data.lower()


class TestAuthorization:
    """Test suite for role-based authorization"""

    def test_non_admin_cannot_access_settings(self, client, test_user, test_tenant, test_user_2, db_session):
        """Test that non-admin members cannot access workspace settings"""
        from app.models.tenant import TenantMembership

        # Add test_user_2 as regular member (not admin)
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Login as test_user_2 (regular member)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user_2.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access settings
        response = client.get('/tenant/settings')

        # Should be denied
        assert response.status_code in [403, 302]  # Forbidden or redirect with flash

    def test_admin_can_access_settings(self, client, test_user, test_tenant):
        """Test that admins can access workspace settings"""
        # Login as test_user (owner)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to access settings
        response = client.get('/tenant/settings')

        # Should be allowed
        assert response.status_code == 200

    def test_non_admin_cannot_invite_users(self, client, test_user, test_tenant, test_user_2, db_session):
        """Test that non-admin members cannot invite users"""
        from app.models.tenant import TenantMembership

        # Add test_user_2 as regular member (not admin)
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Login as test_user_2 (regular member)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user_2.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to invite a user
        response = client.post('/tenant/invite', data={
            'email': 'newmember@example.com',
            'role': 'member'
        })

        # Should be denied
        assert response.status_code in [403, 302]  # Forbidden or redirect
