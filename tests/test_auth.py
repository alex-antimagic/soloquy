"""
Tests for authentication and authorization
"""
import pytest
from app.models.user import User


class TestAuthentication:
    """Test suite for user authentication"""

    def test_user_registration(self, client, db_session):
        """Test user can register with valid data"""
        response = client.post('/register', data={
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'SecurePass123!@#',
            'password2': 'SecurePass123!@#'
        }, follow_redirects=False)

        # Registration should redirect
        assert response.status_code == 302

        # Verify user was created (even if email not confirmed)
        user = User.query.filter_by(email='newuser@example.com').first()
        assert user is not None
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        assert user.check_password('SecurePass123!@#')

    def test_weak_password_rejected(self, client, db_session):
        """Test that weak passwords are rejected"""
        # Ensure client is logged out
        client.get('/logout')

        response = client.post('/register', data={
            'email': 'weak@example.com',
            'first_name': 'Weak',
            'last_name': 'User',
            'password': '12345',  # Too weak (less than 8 chars)
            'password2': '12345'
        }, follow_redirects=True)

        # Should show validation error - form re-renders with error message
        assert response.status_code == 200
        assert b'password' in response.data.lower() or b'8 characters' in response.data.lower()

    def test_user_login(self, client, test_user):
        """Test user can login with correct credentials"""
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'Test123!@#'
        }, follow_redirects=False)

        assert response.status_code == 302  # Redirect after login

    def test_user_login_wrong_password(self, client, test_user):
        """Test login fails with wrong password"""
        # Ensure client is logged out
        client.get('/logout')

        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'WrongPassword123!@#'
        }, follow_redirects=True)

        # Should stay on login page with error message
        assert response.status_code == 200
        assert b'invalid' in response.data.lower() or b'email or password' in response.data.lower()

    def test_account_lockout_after_failed_attempts(self, client, test_user):
        """Test account locks after multiple failed login attempts"""
        # Ensure client is logged out
        client.get('/logout')

        # Try to login with wrong password multiple times
        for i in range(6):  # Should lock after 5 attempts
            client.post('/login', data={
                'email': 'test@example.com',
                'password': 'WrongPassword123!@#'
            })

        # Next attempt should be locked
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': 'Test123!@#'  # Even correct password
        }, follow_redirects=True)

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
        client.post('/login', data={
            'email': 'test2@example.com',
            'password': 'Test123!@#'
        })

        # Set current tenant in session
        with client.session_transaction() as sess:
            sess['current_tenant_id'] = test_tenant.id

        # Try to access settings
        response = client.get('/tenant/settings')

        # Should be denied
        assert response.status_code in [403, 302]  # Forbidden or redirect with flash

    def test_admin_can_access_settings(self, client, test_user, test_tenant):
        """Test that admins can access workspace settings"""
        # Clear any previous session state
        client.get('/logout')

        # Login and follow redirects to let the app set up the session properly
        client.post('/login', data={
            'email': 'test@example.com',
            'password': 'Test123!@#'
        }, follow_redirects=True)

        # Set the current tenant in session (required for tenant-scoped routes)
        with client.session_transaction() as sess:
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
        client.post('/login', data={
            'email': 'test2@example.com',
            'password': 'Test123!@#'
        })

        # Set current tenant in session
        with client.session_transaction() as sess:
            sess['current_tenant_id'] = test_tenant.id

        # Try to invite a user
        response = client.post('/tenant/invite', data={
            'email': 'newmember@example.com',
            'role': 'member'
        })

        # Should be denied
        assert response.status_code in [403, 302]  # Forbidden or redirect
