# worklead Test Suite

Comprehensive test suite for the worklead multi-tenant SaaS application.

## Setup

Install test dependencies:

```bash
pip install pytest pytest-flask pytest-cov
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run with verbose output:
```bash
pytest -v
```

### Run specific test file:
```bash
pytest tests/test_auth.py
```

### Run specific test:
```bash
pytest tests/test_auth.py::TestAuthentication::test_user_login
```

### Run tests by marker:
```bash
# Run only security tests
pytest -m security

# Run everything except slow tests
pytest -m "not slow"
```

### Generate coverage report:
```bash
pytest --cov=app --cov-report=html --cov-report=term
```

Then open `htmlcov/index.html` in your browser.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest fixtures and configuration
├── test_auth.py                # Authentication & authorization tests
├── test_tenant_isolation.py    # Tenant isolation security tests
└── README.md                   # This file
```

## Test Fixtures

Common fixtures available in all tests (defined in `conftest.py`):

- `app` - Flask application instance
- `client` - Test client for making requests
- `db_session` - Database session (automatically rolled back after each test)
- `test_user` - Default test user
- `test_user_2` - Second test user for multi-user scenarios
- `test_tenant` - Default test tenant/workspace
- `test_tenant_2` - Second test tenant for cross-tenant testing
- `test_department` - Default test department
- `authenticated_client` - Pre-authenticated test client

## Writing New Tests

### Basic test structure:

```python
class TestMyFeature:
    """Test suite for my feature"""

    def test_something(self, client, test_user):
        """Test that something works"""
        # Arrange
        # ... setup

        # Act
        response = client.get('/some/endpoint')

        # Assert
        assert response.status_code == 200
```

### Testing authenticated routes:

```python
def test_protected_route(self, client, test_user, test_tenant):
    """Test accessing a protected route"""
    # Set up session
    with client.session_transaction() as sess:
        sess['user_id'] = test_user.id
        sess['current_tenant_id'] = test_tenant.id

    # Make request
    response = client.get('/protected/route')
    assert response.status_code == 200
```

## Test Categories

Use pytest markers to categorize tests:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.security` - Security tests
- `@pytest.mark.auth` - Authentication/authorization tests
- `@pytest.mark.slow` - Slow-running tests

Example:
```python
@pytest.mark.security
@pytest.mark.integration
def test_tenant_isolation(self, ...):
    pass
```

## Coverage Goals

- **Overall:** 70%+ code coverage
- **Security-critical code:** 90%+ coverage
- **Authentication/Authorization:** 95%+ coverage
- **Tenant isolation:** 100% coverage

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to main branch
- Nightly builds

## Current Test Coverage

Run `pytest --cov=app --cov-report=term` to see current coverage.

**Priority areas for testing:**
1. ✅ Tenant isolation security
2. ✅ Authentication and authorization
3. TODO: CRM workflows
4. TODO: Task management
5. TODO: Department/Agent management
6. TODO: Integration endpoints

## Troubleshooting

### Database errors:
```bash
# Reset test database
rm -f test.db
pytest
```

### Import errors:
```bash
# Ensure PYTHONPATH includes app directory
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest
```

### Redis connection errors:
Make sure Redis is running or tests that require Redis will be skipped:
```bash
redis-server
```
