"""
Pytest configuration and fixtures for Soloquy tests
"""
import pytest
from app import create_app, db
from app.models.user import User
from app.models.tenant import Tenant, TenantMembership
from app.models.department import Department
from config import TestingConfig


@pytest.fixture(scope='session')
def app():
    """Create and configure a test application instance"""
    app = create_app('testing')

    # Establish an application context
    ctx = app.app_context()
    ctx.push()

    yield app

    ctx.pop()


@pytest.fixture(scope='session')
def _db(app):
    """Create test database"""
    db.create_all()
    yield db
    db.session.close()
    db.drop_all()


@pytest.fixture(scope='function')
def db_session(_db):
    """Create a new database session for each test"""
    connection = _db.engine.connect()
    transaction = connection.begin()

    session = _db.session
    session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        email_confirmed=True
    )
    user.set_password('Test123!@#')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_user_2(db_session):
    """Create a second test user"""
    user = User(
        email='test2@example.com',
        first_name='Test',
        last_name='User2',
        email_confirmed=True
    )
    user.set_password('Test123!@#')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_tenant(db_session, test_user):
    """Create a test tenant with the test user as owner"""
    tenant = Tenant(
        name='Test Workspace',
        slug='test-workspace'
    )
    db_session.add(tenant)
    db_session.flush()

    # Add user as owner
    membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=test_user.id,
        role='owner'
    )
    db_session.add(membership)
    db_session.commit()

    return tenant


@pytest.fixture
def test_tenant_2(db_session, test_user_2):
    """Create a second test tenant with test_user_2 as owner"""
    tenant = Tenant(
        name='Test Workspace 2',
        slug='test-workspace-2'
    )
    db_session.add(tenant)
    db_session.flush()

    # Add user as owner
    membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=test_user_2.id,
        role='owner'
    )
    db_session.add(membership)
    db_session.commit()

    return tenant


@pytest.fixture
def test_department(db_session, test_tenant):
    """Create a test department"""
    department = Department(
        name='Test Department',
        slug='test-department',
        tenant_id=test_tenant.id,
        color='#0000FF'
    )
    db_session.add(department)
    db_session.commit()
    return department


@pytest.fixture
def authenticated_client(client, test_user):
    """Create an authenticated test client"""
    with client.session_transaction() as sess:
        sess['user_id'] = test_user.id
        sess['_fresh'] = True
    return client
