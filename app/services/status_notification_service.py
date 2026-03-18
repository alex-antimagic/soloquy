"""
Status Page Notification Service
Handles email notifications for status updates
"""
from app import db
from app.services.email_service import email_service
from app.models.status_subscriber import StatusSubscriber
from app.models.status_incident import StatusIncident
from flask import url_for
from datetime import datetime


def send_subscription_confirmation(subscriber, website, tenant):
    """Send email to confirm subscription"""
    if not email_service.client:
        return False

    confirmation_url = url_for('public_bp.confirm_subscription',
                               tenant_slug=tenant.slug,
                               token=subscriber.confirmation_token,
                               _external=True)

    subject = f"Confirm your subscription to {website.title} status updates"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; border-radius: 8px; }}
        .header {{ background: #667eea; color: white; padding: 40px 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ padding: 40px 30px; }}
        .button {{ display: inline-block; background: #667eea; color: white; text-decoration: none; padding: 14px 40px; border-radius: 6px; font-weight: 600; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Confirm Your Subscription</h1>
        </div>
        <div class="content">
            <p>Thanks for subscribing to status updates for {website.title}!</p>
            <p>Click the button below to confirm your subscription:</p>
            <p><a href="{confirmation_url}" class="button">Confirm Subscription</a></p>
            <p>If you didn't request this, you can safely ignore this email.</p>
        </div>
    </div>
</body>
</html>
    """

    try:
        from sendgrid.helpers.mail import Mail, Email, To, Content
        message = Mail(
            from_email=Email(email_service.from_email, website.title),
            to_emails=To(subscriber.email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        response = email_service.client.send(message)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Error sending subscription confirmation: {e}")
        return False


def send_incident_notification(incident, update, notification_type='created'):
    """
    Send incident notification to all active subscribers

    Args:
        incident: StatusIncident instance
        update: IncidentUpdate instance
        notification_type: 'created', 'updated', or 'resolved'
    """
    if not email_service.client:
        return

    # Get active subscribers
    subscribers = StatusSubscriber.query.filter_by(
        config_id=incident.config_id,
        confirmed=True,
        is_active=True
    ).all()

    if not subscribers:
        return

    # Get website for branding
    from app.models.website import Website
    from app.models.status_page_config import StatusPageConfig
    from app.models.tenant import Tenant

    website = Website.query.join(StatusPageConfig).filter(
        StatusPageConfig.id == incident.config_id
    ).first()

    if not website:
        return

    tenant = website.tenant

    # Build status page URL
    status_url = url_for('public_bp.incident_detail',
                        tenant_slug=tenant.slug,
                        incident_id=incident.id,
                        _external=True)

    # Email subject based on type
    if notification_type == 'created':
        subject = f"[{incident.severity.upper()}] {incident.title}"
    elif notification_type == 'resolved':
        subject = f"[RESOLVED] {incident.title}"
    else:
        subject = f"[UPDATE] {incident.title}"

    # Severity color
    severity_colors = {
        'minor': '#f59e0b',
        'major': '#ef4444',
        'critical': '#dc2626'
    }
    color = severity_colors.get(incident.severity, '#ef4444')

    # Build email for each subscriber
    for subscriber in subscribers:
        unsubscribe_url = url_for('public_bp.unsubscribe',
                                  tenant_slug=tenant.slug,
                                  token=subscriber.unsubscribe_token,
                                  _external=True)

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; border-radius: 8px; }}
        .header {{ background: {color}; color: white; padding: 40px 30px; border-radius: 8px 8px 0 0; }}
        .content {{ padding: 40px 30px; }}
        .update {{ background: #f8f9fa; padding: 15px; border-left: 4px solid {color}; margin: 20px 0; }}
        .button {{ display: inline-block; background: #667eea; color: white; text-decoration: none; padding: 14px 40px; border-radius: 6px; font-weight: 600; }}
        .footer {{ padding: 20px 30px; text-align: center; color: #666; font-size: 14px; background: #f8f9fa; border-radius: 0 0 8px 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{subject}</h1>
            <p>{incident.severity.upper()} Incident</p>
        </div>
        <div class="content">
            <p><strong>Latest Update:</strong></p>
            <div class="update">
                <p>{update.message}</p>
                <p style="font-size: 14px; color: #666; margin-top: 10px;">
                    {update.created_at.strftime('%B %d, %Y at %I:%M %p UTC')}
                </p>
            </div>
            <p><a href="{status_url}" class="button">View Full Status Page</a></p>
        </div>
        <div class="footer">
            <p>You're receiving this because you subscribed to {website.title} status updates.</p>
            <p><a href="{unsubscribe_url}">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>
        """

        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content
            message = Mail(
                from_email=Email(email_service.from_email, f"{website.title} Status"),
                to_emails=To(subscriber.email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            email_service.client.send(message)
        except Exception as e:
            print(f"Error sending incident notification to {subscriber.email}: {e}")

    # Mark as sent
    if notification_type == 'created':
        incident.notification_sent = True
        incident.notification_sent_at = datetime.utcnow()

    update.notification_sent = True
    update.notification_sent_at = datetime.utcnow()
    db.session.commit()
