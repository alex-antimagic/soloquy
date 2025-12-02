# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions for continuous integration and deployment. Every pull request is tested automatically, and successful merges to `main` are automatically deployed to Heroku.

## Workflow

### On Pull Request
1. **Test Job**: Runs all tests with pytest
   - Sets up PostgreSQL and Redis services
   - Runs database migrations
   - Executes test suite with coverage reporting
   - Must pass before merge is allowed

### On Push to Main
1. **Test Job**: Same as PR (runs first)
2. **Deploy Job**: Deploys to Heroku (only if tests pass)
   - Uses Heroku API key for authentication
   - Deploys to `soloquy-dev` app
   - Sends deployment notifications

## Required GitHub Secrets

Configure these in your GitHub repository settings (Settings → Secrets and variables → Actions):

1. **ANTHROPIC_API_KEY**
   - Your Anthropic API key for AI features
   - Required for tests that use AI agents

2. **HEROKU_API_KEY**
   - Your Heroku API key for deployments
   - Get it from: `heroku auth:token`

3. **HEROKU_EMAIL**
   - Email associated with your Heroku account

## Local Testing

To run the same tests locally:

```bash
# Set up test database
createdb soloquy_test

# Run migrations
FLASK_ENV=testing python3 -c "from app import create_app; from flask_migrate import upgrade; app = create_app('testing'); with app.app_context(): upgrade()"

# Run tests
FLASK_ENV=testing pytest tests/ -v --cov=app
```

## Coverage Requirements

- Current coverage: ~40-50%
- Target coverage: 80%
- Tests will pass at current coverage but should be improved over time

## Failure Scenarios

### Tests Fail
- PR cannot be merged until tests pass
- Check the Actions tab for detailed error logs
- Fix issues and push again

### Deployment Fails
- Main branch is protected
- Heroku deployment failure does not rollback main
- Check Heroku logs: `heroku logs --tail -a soloquy-dev`

## Adding New Tests

When adding new features:
1. Write tests first (TDD)
2. Ensure tests pass locally
3. Create PR - CI will run automatically
4. Merge after approval and passing tests

## Notifications

- GitHub will show check status on PRs
- Failed checks block merging (if branch protection is enabled)
- Deployment success/failure is logged in Actions output
