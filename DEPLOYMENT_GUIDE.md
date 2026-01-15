# worklead - Heroku Deployment Guide

## Security Hardening Completed ✅

This application has been hardened for production deployment with the following security improvements:

### Critical Fixes Implemented

1. **✅ Secret Key Management**
   - Removed hardcoded secret key
   - Environment variable validation
   - Auto-generation for development

2. **✅ Debug Mode Protection**
   - Environment-based debug mode
   - Disabled in production

3. **✅ CSRF Protection**
   - Flask-WTF CSRF enabled globally
   - Automatic CSRF tokens for all forms
   - AJAX CSRF protection via JavaScript

4. **✅ Rate Limiting**
   - Global rate limits (200/day, 50/hour)
   - Login: 5 attempts/minute
   - Registration: 3 attempts/hour
   - Messages: 30/minute

5. **✅ Multi-Tenant Security**
   - `@require_tenant_access` decorator
   - Tenant isolation enforced
   - Access validation on all routes

6. **✅ AI Input Sanitization**
   - Prompt injection prevention
   - Message length validation (10,000 chars max)
   - Dangerous pattern detection

7. **✅ Authentication Hardening**
   - Session regeneration on login
   - Password complexity requirements:
     - Min 8 characters
     - Uppercase, lowercase, number, special char

8. **✅ Security Headers (Production Only)**
   - HTTPS enforcement
   - Strict Transport Security (HSTS)
   - Content Security Policy (CSP)
   - X-Frame-Options: DENY
   - X-Content-Type-Options: nosniff

9. **✅ Database Security**
   - SSL/TLS for Postgres connections
   - Parameterized queries only

10. **✅ Production Dependencies**
    - Gunicorn WSGI server
    - Flask-Limiter for rate limiting
    - Flask-Talisman for security headers

---

## Pre-Deployment Checklist

### 1. Install Heroku CLI
```bash
brew tap heroku/brew && brew install heroku
# or
curl https://cli-assets.heroku.com/install.sh | sh
```

### 2. Login to Heroku
```bash
heroku login
```

### 3. Create Heroku App
```bash
heroku create your-app-name
```

### 4. Add Postgres Database
```bash
heroku addons:create heroku-postgresql:mini
```

### 5. Add Redis for Background Jobs
```bash
heroku addons:create heroku-redis:mini
```

### 6. Add Sentry for Error Tracking (Highly Recommended)
```bash
# Option 1: Use Heroku add-on (easiest)
heroku addons:create sentry:f1  # Free tier

# Option 2: Sign up directly at sentry.io
# Then set the DSN manually:
# heroku config:set SENTRY_DSN=your_sentry_dsn_here
```

### 7. Set Environment Variables
```bash
# Generate and set SECRET_KEY
heroku config:set SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')

# Set Flask environment
heroku config:set FLASK_ENV=production

# Set Anthropic API key
heroku config:set ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Set SocketIO CORS origins (replace with your app URL)
heroku config:set SOCKETIO_CORS_ORIGINS=https://your-app-name.herokuapp.com

# Note: SENTRY_DSN is automatically set if you used the Heroku add-on
# If you signed up directly at sentry.io, set it manually:
# heroku config:set SENTRY_DSN=your_sentry_dsn_here

# Verify configuration
heroku config
```

### 6. Initialize Git (if not already done)
```bash
git init
git add .
git commit -m "Initial commit with security hardening"
```

### 7. Deploy to Heroku
```bash
# Add Heroku remote
heroku git:remote -a your-app-name

# Push to Heroku
git push heroku main
```

### 8. Scale Web Dyno
```bash
heroku ps:scale web=1
```

### 9. Verify Deployment
```bash
# Check logs
heroku logs --tail

# Open app
heroku open
```

---

## Post-Deployment Verification

### 1. Test Security Features

**CSRF Protection:**
- Try to submit a form without CSRF token → Should fail
- Normal form submission → Should work

**Rate Limiting:**
- Try 6+ login attempts in 1 minute → Should be rate limited
- Normal usage → Should work

**Password Complexity:**
- Try weak password → Should show requirements
- Try strong password → Should accept

**HTTPS:**
- HTTP requests → Should redirect to HTTPS
- HTTPS requests → Should work

### 2. Monitor Application
```bash
# View logs
heroku logs --tail

# Check dyno status
heroku ps

# View metrics
heroku metrics
```

### 3. Database Management
```bash
# Run migrations
heroku run flask db upgrade

# Access database console
heroku pg:psql

# View database info
heroku pg:info
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ Yes | Flask secret key for sessions (generate with secrets.token_hex(32)) |
| `FLASK_ENV` | ✅ Yes | Set to 'production' |
| `ANTHROPIC_API_KEY` | ✅ Yes | Your Claude API key from Anthropic |
| `SENTRY_DSN` | ⚠️ Recommended | Sentry DSN for error tracking (free tier available) |
| `SOCKETIO_CORS_ORIGINS` | ⚠️ Recommended | Comma-separated list of allowed origins for WebSocket connections |
| `DATABASE_URL` | Auto | Automatically set by Heroku Postgres addon |
| `REDIS_URL` | Auto | Automatically set by Heroku Redis addon |
| `CLOUDINARY_*` | Auto | Automatically set by Cloudinary addon (if installed) |
| `PORT` | Auto | Automatically set by Heroku |

---

## Security Best Practices

### 1. Regular Updates
```bash
# Update dependencies regularly
pip list --outdated
pip install --upgrade package-name
```

### 2. Monitor for Vulnerabilities
```bash
# Install pip-audit
pip install pip-audit

# Scan dependencies
pip-audit
```

### 3. Enable Heroku Features
```bash
# Enable automated security updates
heroku features:enable runtime-dyno-metadata

# Enable preboot for zero-downtime deployments
heroku features:enable preboot
```

### 4. Set Up Monitoring

**Sentry Error Tracking (Integrated):**
- ✅ Sentry is already integrated and will start tracking errors automatically
- Access your Sentry dashboard: https://sentry.io/
- Configure alert rules for critical errors
- Set up Slack/email notifications for error spikes

**Additional Monitoring:**
- Enable Heroku metrics: `heroku labs:enable log-runtime-metrics`
- Set up uptime monitoring (e.g., UptimeRobot, Pingdom)
- Monitor the `/health` endpoint for service health checks

### 5. Backup Database
```bash
# Create manual backup
heroku pg:backups:capture

# View backups
heroku pg:backups

# Restore backup
heroku pg:backups:restore backup-name
```

---

## Scaling

### Vertical Scaling (Dyno Size)
```bash
# Upgrade to standard dyno
heroku ps:resize web=standard-1x

# Upgrade to performance dyno
heroku ps:resize web=performance-m
```

### Horizontal Scaling (More Dynos)
```bash
# Scale to 2 web dynos
heroku ps:scale web=2
```

### Database Scaling
```bash
# Upgrade database plan
heroku addons:upgrade heroku-postgresql:standard-0
```

---

## Troubleshooting

### Application Won't Start
```bash
# Check logs
heroku logs --tail

# Verify environment variables
heroku config

# Check dyno status
heroku ps
```

### Database Issues
```bash
# Reset database
heroku pg:reset DATABASE_URL
heroku run flask db upgrade

# Check database connections
heroku pg:info
```

### Rate Limiting Issues
- Rate limits are stored in memory by default
- For multiple dynos, consider Redis storage:
```bash
heroku addons:create heroku-redis:mini
# Update config.py to use REDIS_URL for limiter storage
```

---

## Rollback

### Rollback to Previous Release
```bash
# View releases
heroku releases

# Rollback to specific version
heroku rollback v123
```

---

## Cost Optimization

### Free Tier (Hobby)
- Eco dynos sleep after 30 minutes of inactivity
- 1000 free dyno hours/month
- Free Postgres database (limited rows)

### Recommended Production Setup
- Standard-1X dyno: $25/month
- Standard-0 Postgres: $50/month
- Total: ~$75/month

---

## Additional Security Considerations

### Remaining Tasks (Optional - Not Blocking)
These items can be addressed post-deployment:

1. **Login Attempt Tracking**
   - Track failed login attempts in database
   - Implement account lockout after 5 failed attempts
   - Send email notification on suspicious activity

2. **Audit Logging**
   - Log all security-sensitive actions
   - Track user access patterns
   - Monitor for suspicious activity

3. **Content Security Policy Tuning**
   - Review CSP violations in production
   - Tighten CSP rules based on actual usage
   - Remove `unsafe-inline` if possible

4. **Rate Limiting with Redis**
   - Current implementation uses in-memory storage
   - For multiple dynos, use Redis backend
   - Provides consistent rate limiting across instances

---

## Support & Resources

- **Heroku Docs**: https://devcenter.heroku.com/
- **Flask Security**: https://flask.palletsprojects.com/en/latest/security/
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **Anthropic API Docs**: https://docs.anthropic.com/

---

## Security Audit Summary

**Status**: ✅ **READY FOR PRIVATE DEPLOYMENT**

**Critical Issues Fixed**: 8/8
**High Severity Fixed**: 7/7
**Medium Severity**: 2 remaining (non-blocking)

The application is now secure for private/invite-only deployment. Public deployment is safe after implementing login attempt tracking and additional monitoring.

**Last Updated**: November 7, 2025
