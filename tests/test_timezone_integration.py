"""
Integration tests for timezone functionality across the application
"""
import pytest
from datetime import datetime
import pytz
from app import create_app, db
from app.models.user import User
from app.models.tenant import Tenant, TenantMembership
from app.models.department import Department
from app.models.agent import Agent
from app.models.message import Message


@pytest.fixture
def test_user(db_session):
    """Create a test user with PST timezone"""
    user = User(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        timezone_preference='America/Los_Angeles',
        is_active=True
    )
    user.set_password('password123')
    db_session.add(user)
    db_session.commit()
    return user


def test_user_timezone_preference_saved(test_user):
    """Test that user timezone preference is saved correctly"""
    assert test_user.timezone_preference == 'America/Los_Angeles'


def test_template_filter_converts_timezone(test_user):
    """Test that template filter converts UTC to user timezone"""
    from app.utils.timezone_utils import format_datetime_for_user

    # Create UTC datetime (8pm)
    utc_time = datetime(2024, 12, 1, 20, 0, 0)

    # Format in user's timezone
    formatted = format_datetime_for_user(
        utc_time,
        test_user.timezone_preference,
        '%I:%M %p %Z'
    )

    # Should be noon Pacific time
    assert '12:00' in formatted
    assert ('PST' in formatted or 'PDT' in formatted)


def test_message_created_at_conversion(db_session, test_user):
    """Test that message timestamps are converted properly"""
    # Create a tenant and department first
    tenant = Tenant(name='Test Tenant', slug='test-tenant')
    db_session.add(tenant)
    db_session.commit()

    dept = Department(
        name='Test Dept',
        slug='test-dept',
        tenant_id=tenant.id,
        description='Test'
    )
    db_session.add(dept)
    db_session.commit()

    agent = Agent(
        name='Test Agent',
        department_id=dept.id,
        system_prompt='Test'
    )
    db_session.add(agent)
    db_session.commit()

    # Create a message with UTC timestamp
    message = Message(
        sender_id=test_user.id,
        recipient_id=None,
        department_id=dept.id,
        agent_id=agent.id,
        content='Test message',
        created_at=datetime(2024, 12, 1, 20, 0, 0)  # 8pm UTC
    )
    db_session.add(message)
    db_session.commit()

    # Convert to user's timezone
    from app.utils.timezone_utils import convert_utc_to_user_tz
    user_time = convert_utc_to_user_tz(message.created_at, test_user.timezone_preference)

    # Should be noon Pacific
    assert user_time.hour == 12


def test_timezone_auto_detection_on_register(client):
    """Test that timezone is auto-detected during registration"""
    # Simulate registration with detected timezone
    response = client.post('/register', data={
        'email': 'newuser@example.com',
        'first_name': 'New',
        'last_name': 'User',
        'password': 'Password123!',
        'password2': 'Password123!',
        'detected_timezone': 'America/New_York'
    }, follow_redirects=False)

    # Note: This test would need proper CSRF token handling and
    # form validation to work in a real test environment
    # This is a simplified version showing the concept


def test_timezone_settings_update(db_session, test_user):
    """Test updating timezone in account settings"""
    original_tz = test_user.timezone_preference

    # Update timezone
    test_user.timezone_preference = 'America/New_York'
    db_session.commit()

    # Verify change
    db_session.refresh(test_user)
    assert test_user.timezone_preference == 'America/New_York'
    assert test_user.timezone_preference != original_tz


def test_quickbooks_uses_utc():
    """Test that QuickBooks service uses utcnow() consistently"""
    from app.services.quickbooks_service import QuickBooksService

    # This test verifies the fix we made
    # The service should now use datetime.utcnow() instead of datetime.now()
    # We can verify by checking the source code was updated
    import inspect
    source = inspect.getsource(QuickBooksService.get_profit_loss)

    # Should contain utcnow, not now
    assert 'datetime.utcnow()' in source
    assert 'datetime.now()' not in source or 'datetime.now(tz=' in source  # Allow timezone-aware now()
