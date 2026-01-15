# Email Setup Guide for worklead.ai

## Current Status
✅ Domain: worklead.ai is active and resolving
✅ DMARC: Already configured
⚠️ SPF: Not configured (required for email sending)
⚠️ MX Records: Not configured (required for email receiving)
⚠️ SendGrid Domain Authentication: Needs setup

## Required Steps

### 1. Configure SendGrid Domain Authentication

SendGrid domain authentication ensures your emails don't go to spam and improves deliverability.

**Steps:**
1. Log in to [SendGrid Dashboard](https://app.sendgrid.com)
2. Navigate to **Settings** → **Sender Authentication**
3. Click **Authenticate Your Domain**
4. Enter domain: `worklead.ai`
5. Select DNS host: **Cloudflare** (or your DNS provider)
6. SendGrid will provide DNS records to add

**Expected DNS Records from SendGrid:**
You'll need to add these to Cloudflare:

```
Type: CNAME
Name: s1._domainkey.worklead.ai
Value: s1.domainkey.u[XXXXX].wl.sendgrid.net

Type: CNAME
Name: s2._domainkey.worklead.ai
Value: s2.domainkey.u[XXXXX].wl.sendgrid.net

Type: CNAME
Name: em[XXXX].worklead.ai
Value: u[XXXXX].wl.sendgrid.net
```

### 2. Add SPF Record (Required for Email Sending)

**Add to Cloudflare DNS:**
```
Type: TXT
Name: @ (or worklead.ai)
Value: v=spf1 include:sendgrid.net ~all
TTL: Auto
```

This authorizes SendGrid to send emails on behalf of worklead.ai.

### 3. Update DMARC Record (Recommended)

Your current DMARC policy is set to `quarantine`. Update it to include a reporting email:

**Update in Cloudflare DNS:**
```
Type: TXT
Name: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:dmarc@worklead.ai; pct=100; adkim=r; aspf=r
```

### 4. Add MX Records (Only if receiving email)

If you want to receive emails at @worklead.ai addresses:

**Option A: Google Workspace**
```
Type: MX, Priority: 1, Value: aspmx.l.google.com
Type: MX, Priority: 5, Value: alt1.aspmx.l.google.com
Type: MX, Priority: 5, Value: alt2.aspmx.l.google.com
Type: MX, Priority: 10, Value: alt3.aspmx.l.google.com
Type: MX, Priority: 10, Value: alt4.aspmx.l.google.com
```

**Option B: Forward to Gmail (using Cloudflare Email Routing - Free)**
1. Go to Cloudflare Dashboard → Email Routing
2. Enable Email Routing for worklead.ai
3. Add destination address (your personal email)
4. Add routing rules (e.g., noreply@worklead.ai → your.email@gmail.com)

### 5. Verify SendGrid Configuration

After adding DNS records:

1. **Wait 24-48 hours** for DNS propagation (usually faster)
2. Go back to SendGrid → Sender Authentication
3. Click **Verify** next to your domain
4. SendGrid will confirm authentication status

### 6. Test Email Sending

Once verified, test email sending:

```bash
# From your Heroku app
heroku run python -a worklead
>>> from app.services.email_service import email_service
>>> from app.models.user import User
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
...     user = User.query.first()
...     email_service.send_welcome_email(user)
```

Or use SendGrid's test feature in the dashboard.

## Current Heroku Email Configuration

✅ **Updated Environment Variables:**
```
MAIL_DEFAULT_SENDER=noreply@worklead.ai
MAIL_ADMIN_EMAIL=admin@worklead.ai
SENDGRID_FROM_EMAIL=noreply@worklead.ai
SENDGRID_FROM_NAME=worklead
```

## Verification Checklist

- [ ] SendGrid domain authenticated
- [ ] SPF record added and verified (use [MXToolbox](https://mxtoolbox.com/spf.aspx))
- [ ] DKIM records added (from SendGrid)
- [ ] DMARC record updated
- [ ] Test email sent successfully
- [ ] Email doesn't land in spam folder
- [ ] All emails display "worklead" as sender name

## Troubleshooting

### Emails going to spam
- Verify SPF, DKIM, and DMARC are all configured correctly
- Warm up your domain by sending gradually increasing volumes
- Avoid spam trigger words in subject lines
- Ensure unsubscribe links are present

### DNS not propagating
```bash
# Check DNS propagation
dig worklead.ai TXT +short
dig s1._domainkey.worklead.ai CNAME +short
dig s2._domainkey.worklead.ai CNAME +short
```

### SendGrid authentication failing
- Double-check all CNAME values match exactly
- Wait up to 48 hours for DNS propagation
- Clear your DNS cache: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`

## Resources

- [SendGrid Domain Authentication](https://docs.sendgrid.com/ui/account-and-settings/how-to-set-up-domain-authentication)
- [SPF Record Checker](https://mxtoolbox.com/spf.aspx)
- [DMARC Analyzer](https://mxtoolbox.com/dmarc.aspx)
- [Email Deliverability Guide](https://sendgrid.com/resource/email-deliverability-guide/)
