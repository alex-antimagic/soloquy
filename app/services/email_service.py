"""
Email Service
Sends emails using Twilio SendGrid
"""
import os
from flask import url_for

# Try to import sendgrid - gracefully handle if not installed
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("Warning: sendgrid package not installed. Email sending will be disabled.")


class EmailService:
    """Service for sending emails via Twilio SendGrid"""

    def __init__(self):
        """Initialize SendGrid client"""
        self.api_key = os.environ.get('SENDGRID_API_KEY')
        self.from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@worklead.ai')
        self.from_name = os.environ.get('SENDGRID_FROM_NAME', 'worklead')

        if not SENDGRID_AVAILABLE:
            print("Warning: sendgrid package not installed. Email sending will be disabled.")
            self.client = None
        elif not self.api_key:
            print("Warning: SENDGRID_API_KEY not configured. Email sending will be disabled.")
            self.client = None
        else:
            self.client = SendGridAPIClient(self.api_key)

    def send_invitation_email(self, invitation, inviter_name, workspace_name):
        """
        Send workspace invitation email

        Args:
            invitation: Invitation model instance
            inviter_name: Name of the user who sent the invitation
            workspace_name: Name of the workspace

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.client:
            print(f"Skipping email send to {invitation.email} (SendGrid not configured)")
            return False

        try:
            # Build invitation URL
            invitation_url = url_for('tenant.accept_invitation',
                                    token=invitation.token,
                                    _external=True)

            # Email subject
            subject = f"{inviter_name} invited you to join {workspace_name} on worklead"

            # HTML email content
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 16px;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .content p {{
            margin: 0 0 20px 0;
            font-size: 16px;
        }}
        .workspace-info {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px 20px;
            margin: 25px 0;
        }}
        .workspace-info strong {{
            color: #667eea;
        }}
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 14px 40px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 16px;
            margin: 20px 0;
        }}
        .cta-button:hover {{
            opacity: 0.9;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 You're Invited!</h1>
            <p>Join your team on worklead</p>
        </div>

        <div class="content">
            <p>Hi there,</p>

            <p><strong>{inviter_name}</strong> has invited you to join their workspace on worklead.</p>

            <div class="workspace-info">
                <strong>Workspace:</strong> {workspace_name}<br>
                <strong>Role:</strong> {invitation.role.title()}
            </div>

            <p>worklead is an AI-powered workspace platform that helps teams collaborate with intelligent AI agents.</p>

            <center>
                <a href="{invitation_url}" class="cta-button">Accept Invitation</a>
            </center>

            <p style="font-size: 14px; color: #666; margin-top: 30px;">
                This invitation will expire in 7 days. If you have any questions, please contact {inviter_name}.
            </p>
        </div>

        <div class="footer">
            <p>This email was sent by worklead</p>
            <p><a href="https://worklead.ai">Visit worklead</a></p>
        </div>
    </div>
</body>
</html>
            """

            # Plain text fallback
            text_content = f"""
You're invited to join {workspace_name} on worklead!

{inviter_name} has invited you to join their workspace as a {invitation.role}.

Accept your invitation here:
{invitation_url}

This invitation will expire in 7 days.

---
worklead - AI for everyone
            """

            # Create SendGrid message (only if sendgrid is available)
            if not SENDGRID_AVAILABLE:
                print(f"Cannot send email - sendgrid not installed")
                return False

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(invitation.email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            # Send email
            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✓ Invitation email sent to {invitation.email}")
                return True
            else:
                print(f"✗ Failed to send invitation email to {invitation.email}: Status {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error sending invitation email to {invitation.email}: {e}")
            return False

    def send_welcome_email(self, user):
        """
        Send welcome email to new user

        Args:
            user: User model instance

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.client:
            print(f"Skipping welcome email to {user.email} (SendGrid not configured)")
            return False

        try:
            subject = "Welcome to worklead!"

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .content p {{
            margin: 0 0 20px 0;
            font-size: 16px;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to worklead!</h1>
        </div>

        <div class="content">
            <p>Hi {user.first_name or 'there'},</p>

            <p>Welcome to worklead - AI for everyone!</p>

            <p>Your account has been created successfully. You can now create workspaces, invite team members, and collaborate with intelligent AI agents.</p>

            <p>If you have any questions or need help getting started, don't hesitate to reach out.</p>

            <p>Best regards,<br>The worklead Team</p>
        </div>

        <div class="footer">
            <p>This email was sent by worklead</p>
        </div>
    </div>
</body>
</html>
            """

            text_content = f"""
Welcome to worklead!

Hi {user.first_name or 'there'},

Welcome to worklead - AI for everyone!

Your account has been created successfully. You can now create workspaces, invite team members, and collaborate with intelligent AI agents.

If you have any questions or need help getting started, don't hesitate to reach out.

Best regards,
The worklead Team
            """

            # Create SendGrid message (only if sendgrid is available)
            if not SENDGRID_AVAILABLE:
                print(f"Cannot send email - sendgrid not installed")
                return False

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(user.email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✓ Welcome email sent to {user.email}")
                return True
            else:
                print(f"✗ Failed to send welcome email to {user.email}: Status {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error sending welcome email to {user.email}: {e}")
            return False

    def send_password_reset_email(self, user, reset_url):
        """Send password reset email"""
        if not self.client:
            print(f"Skipping password reset email to {user.email} (SendGrid not configured)")
            return False

        try:
            subject = "Reset Your worklead Password"
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
        <div class="header"><h1>Password Reset</h1></div>
        <div class="content">
            <p>Hi {user.first_name or 'there'},</p>
            <p>We received a request to reset your worklead password.</p>
            <p><a href="{reset_url}" class="button">Reset Password</a></p>
            <p>This link will expire in 1 hour. If you didn't request this, please ignore this email.</p>
        </div>
    </div>
</body>
</html>"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(user.email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            response = self.client.send(message)
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"Error sending password reset email: {e}")
            return False

    def send_email_confirmation(self, user, confirmation_url):
        """Send email confirmation"""
        if not self.client:
            print(f"Skipping confirmation email to {user.email} (SendGrid not configured)")
            return False

        try:
            subject = "Confirm Your worklead Email"
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
        <div class="header"><h1>Welcome to worklead!</h1></div>
        <div class="content">
            <p>Hi {user.first_name or 'there'},</p>
            <p>Thanks for signing up! Please confirm your email address to get started.</p>
            <p><a href="{confirmation_url}" class="button">Confirm Email</a></p>
        </div>
    </div>
</body>
</html>"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(user.email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            response = self.client.send(message)
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"Error sending confirmation email: {e}")
            return False

    def send_security_alert_email(self, user, alert_type, details):
        """
        Send security alert email to user

        Args:
            user: User model instance
            alert_type: Type of alert (e.g., 'failed_login', 'account_lockout', 'suspicious_activity')
            details: Dictionary containing alert details (ip_address, location, timestamp, etc.)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.client:
            print(f"Skipping security alert email to {user.email} (SendGrid not configured)")
            return False

        try:
            # Customize subject and message based on alert type
            alert_messages = {
                'failed_login': {
                    'subject': 'Failed Login Attempt on Your Account',
                    'title': '⚠️ Failed Login Attempt',
                    'message': 'We detected a failed login attempt on your account.'
                },
                'account_lockout': {
                    'subject': 'Your Account Has Been Locked',
                    'title': '🔒 Account Locked',
                    'message': 'Your account has been temporarily locked due to multiple failed login attempts.'
                },
                'suspicious_activity': {
                    'subject': 'Suspicious Activity Detected',
                    'title': '⚠️ Suspicious Activity',
                    'message': 'We detected suspicious activity on your account.'
                }
            }

            alert_config = alert_messages.get(alert_type, alert_messages['suspicious_activity'])
            subject = alert_config['subject']

            # Format details for display
            ip_address = details.get('ip_address', 'Unknown')
            timestamp = details.get('timestamp', 'Unknown')
            attempt_count = details.get('attempt_count', 0)

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: #dc3545;
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .content p {{
            margin: 0 0 20px 0;
            font-size: 16px;
        }}
        .alert-box {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px 20px;
            margin: 25px 0;
        }}
        .detail-box {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 15px;
            margin: 20px 0;
            font-family: monospace;
            font-size: 14px;
        }}
        .detail-box div {{
            margin: 5px 0;
        }}
        .cta-button {{
            display: inline-block;
            background: #dc3545;
            color: white;
            text-decoration: none;
            padding: 14px 40px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 16px;
            margin: 20px 0;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{alert_config['title']}</h1>
        </div>

        <div class="content">
            <p>Hi {user.first_name or 'there'},</p>

            <p>{alert_config['message']}</p>

            <div class="alert-box">
                <strong>Security Alert Details:</strong>
            </div>

            <div class="detail-box">
                <div><strong>Time:</strong> {timestamp}</div>
                <div><strong>IP Address:</strong> {ip_address}</div>
                {"<div><strong>Failed Attempts:</strong> " + str(attempt_count) + "</div>" if attempt_count > 0 else ""}
            </div>

            <p><strong>What should you do?</strong></p>
            <ul>
                <li>If this was you, you can safely ignore this email</li>
                <li>If this wasn't you, we recommend changing your password immediately</li>
                <li>Consider enabling two-factor authentication for added security</li>
            </ul>

            <p style="font-size: 14px; color: #666; margin-top: 30px;">
                If you have any concerns or questions about this alert, please contact our support team.
            </p>
        </div>

        <div class="footer">
            <p>This is an automated security alert from worklead</p>
            <p>Please do not reply to this email</p>
        </div>
    </div>
</body>
</html>
            """

            text_content = f"""
{alert_config['title']}

Hi {user.first_name or 'there'},

{alert_config['message']}

Security Alert Details:
- Time: {timestamp}
- IP Address: {ip_address}
{"- Failed Attempts: " + str(attempt_count) if attempt_count > 0 else ""}

What should you do?
- If this was you, you can safely ignore this email
- If this wasn't you, we recommend changing your password immediately
- Consider enabling two-factor authentication for added security

If you have any concerns or questions about this alert, please contact our support team.

---
This is an automated security alert from worklead
Please do not reply to this email
            """

            # Create SendGrid message
            if not SENDGRID_AVAILABLE:
                print(f"Cannot send email - sendgrid not installed")
                return False

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(user.email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✓ Security alert email sent to {user.email}")
                return True
            else:
                print(f"✗ Failed to send security alert email to {user.email}: Status {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error sending security alert email to {user.email}: {e}")
            return False

    # ===== HR EMAIL METHODS =====

    def send_interview_invitation(self, candidate, interview):
        """
        Send interview invitation to candidate

        Args:
            candidate: Candidate model instance
            interview: Interview model instance

        Returns:
            bool: True if email sent successfully
        """
        if not self.client:
            print(f"Skipping interview invitation email to {candidate.email} (SendGrid not configured)")
            return False

        try:
            # Format date and time
            interview_datetime = interview.scheduled_date.strftime('%B %d, %Y at %I:%M %p')

            # Build interviewers list
            interviewers_str = ', '.join(interview.interviewers_list) if interview.interviewers_list else 'the hiring team'

            subject = f"Interview Scheduled: {candidate.position}"

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: #667eea; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -30px -30px 30px; }}
        h1 {{ margin: 0; font-size: 24px; }}
        .details {{ background: #f8f9fa; padding: 15px; border-radius: 4px; margin: 20px 0; }}
        .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Interview Scheduled</h1>
        </div>
        <p>Dear {candidate.first_name},</p>
        <p>We're excited to invite you to interview for the <strong>{candidate.position}</strong> position.</p>
        <div class="details">
            <p><strong>Interview Type:</strong> {interview.interview_type.replace('_', ' ').title()}</p>
            <p><strong>Date & Time:</strong> {interview_datetime}</p>
            <p><strong>Duration:</strong> {interview.duration_minutes} minutes</p>
            {'<p><strong>Location:</strong> ' + interview.location + '</p>' if interview.location else ''}
            <p><strong>Interviewers:</strong> {interviewers_str}</p>
        </div>
        {('<p><strong>Notes:</strong><br>' + interview.notes + '</p>') if interview.notes else ''}
        <p>We look forward to speaking with you!</p>
        <p>Best regards,<br>The Hiring Team</p>
    </div>
</body>
</html>
"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(candidate.email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)
            return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"Error sending interview invitation to {candidate.email}: {e}")
            return False

    def send_candidate_status_update(self, candidate, old_status, new_status, reason=None):
        """
        Send candidate status update notification

        Args:
            candidate: Candidate model instance
            old_status: Previous status
            new_status: New status
            reason: Optional reason for status change

        Returns:
            bool: True if email sent successfully
        """
        if not self.client:
            print(f"Skipping status update email to {candidate.email} (SendGrid not configured)")
            return False

        try:
            # Only send emails for certain status changes
            if new_status not in ['offer_extended', 'hired', 'rejected']:
                return False

            status_messages = {
                'offer_extended': {
                    'subject': f'Job Offer: {candidate.position}',
                    'title': 'Congratulations!',
                    'message': f'We are pleased to extend you an offer for the {candidate.position} position. A member of our team will contact you shortly with details.'
                },
                'hired': {
                    'subject': f'Welcome to the Team!',
                    'title': 'Welcome Aboard!',
                    'message': f'We are excited to have you join our team as {candidate.position}. We will be in touch soon with your start date and onboarding information.'
                },
                'rejected': {
                    'subject': f'Application Update: {candidate.position}',
                    'title': 'Application Update',
                    'message': f'Thank you for your interest in the {candidate.position} position. While we were impressed with your qualifications, we have decided to move forward with other candidates at this time.'
                }
            }

            status_info = status_messages.get(new_status)
            if not status_info:
                return False

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: #667eea; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -30px -30px 30px; }}
        h1 {{ margin: 0; font-size: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{status_info['title']}</h1>
        </div>
        <p>Dear {candidate.first_name},</p>
        <p>{status_info['message']}</p>
        {('<p><strong>Additional notes:</strong> ' + reason + '</p>') if reason else ''}
        <p>Thank you,<br>The Hiring Team</p>
    </div>
</body>
</html>
"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(candidate.email),
                subject=status_info['subject'],
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)
            return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"Error sending status update to {candidate.email}: {e}")
            return False

    def send_onboarding_welcome(self, employee, plan):
        """
        Send welcome email with onboarding plan

        Args:
            employee: Employee model instance
            plan: OnboardingPlan model instance

        Returns:
            bool: True if email sent successfully
        """
        if not self.client:
            print(f"Skipping onboarding welcome email to {employee.email} (SendGrid not configured)")
            return False

        try:
            start_date = plan.start_date.strftime('%B %d, %Y')

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: #10b981; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -30px -30px 30px; }}
        h1 {{ margin: 0; font-size: 24px; }}
        .highlight {{ background: #f0fdf4; padding: 15px; border-left: 4px solid #10b981; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to the Team!</h1>
        </div>
        <p>Dear {employee.first_name},</p>
        <p>We're thrilled to have you joining our team as <strong>{employee.role}</strong> in the {employee.department_name} department!</p>
        <div class="highlight">
            <p><strong>Start Date:</strong> {start_date}</p>
            {('<p><strong>Onboarding Buddy:</strong> ' + plan.buddy_email + '</p>') if plan.buddy_email else ''}
        </div>
        <p>Your personalized onboarding plan has been created with {len(list(plan.tasks.all()))} tasks to help you get started. You'll be able to track your progress and complete items as you go.</p>
        <p>We look forward to seeing you on your first day!</p>
        <p>Best regards,<br>The HR Team</p>
    </div>
</body>
</html>
"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(employee.email),
                subject=f'Welcome to the Team - Your First Day is {start_date}',
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)
            return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"Error sending onboarding welcome to {employee.email}: {e}")
            return False

    def send_onboarding_reminders(self, employee, tasks, include_manager=True):
        """
        Send reminder emails about incomplete onboarding tasks

        Args:
            employee: Employee model instance
            tasks: List of OnboardingTask instances
            include_manager: Whether to CC the manager

        Returns:
            bool: True if email sent successfully
        """
        if not self.client or not tasks:
            return False

        try:
            # Build task list HTML
            task_list_html = ''.join([
                f'<li><strong>{task.title}</strong> - Due: {task.due_date.strftime("%B %d, %Y")}</li>'
                for task in tasks
            ])

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: #f59e0b; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -30px -30px 30px; }}
        h1 {{ margin: 0; font-size: 24px; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ padding: 10px; margin: 5px 0; background: #fef3c7; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Onboarding Reminder</h1>
        </div>
        <p>Hi {employee.first_name},</p>
        <p>Just a friendly reminder about your outstanding onboarding tasks:</p>
        <ul>
            {task_list_html}
        </ul>
        <p>Please complete these tasks at your earliest convenience. If you have any questions, don't hesitate to reach out!</p>
        <p>Best regards,<br>The HR Team</p>
    </div>
</body>
</html>
"""

            # TODO: Add CC to manager if include_manager is True
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(employee.email),
                subject='Onboarding Tasks Reminder',
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)
            return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"Error sending onboarding reminder to {employee.email}: {e}")
            return False

    def send_pto_decision_notification(self, pto_request, action, reason=None):
        """
        Send PTO approval/denial notification

        Args:
            pto_request: PTORequest model instance
            action: 'approve' or 'deny'
            reason: Optional reason for decision

        Returns:
            bool: True if email sent successfully
        """
        if not self.client:
            print(f"Skipping PTO decision email (SendGrid not configured)")
            return False

        try:
            employee = pto_request.employee
            date_range = f"{pto_request.start_date.strftime('%B %d')} - {pto_request.end_date.strftime('%B %d, %Y')}"

            if action == 'approve':
                subject = 'Time Off Request Approved'
                title = 'Request Approved'
                message = f'Your time off request for {date_range} ({pto_request.total_days} days) has been approved.'
                color = '#10b981'
            else:
                subject = 'Time Off Request Update'
                title = 'Request Status'
                message = f'Your time off request for {date_range} has been reviewed.'
                color = '#ef4444'

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -30px -30px 30px; }}
        h1 {{ margin: 0; font-size: 24px; }}
        .details {{ background: #f8f9fa; padding: 15px; border-radius: 4px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
        </div>
        <p>Hi {employee.first_name},</p>
        <p>{message}</p>
        <div class="details">
            <p><strong>Dates:</strong> {date_range}</p>
            <p><strong>Days:</strong> {pto_request.total_days} business days</p>
            <p><strong>Type:</strong> {pto_request.request_type.upper()}</p>
            <p><strong>Status:</strong> {action.title()}d</p>
        </div>
        {('<p><strong>Note:</strong> ' + reason + '</p>') if reason else ''}
        <p>Thank you,<br>The HR Team</p>
    </div>
</body>
</html>
"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(employee.email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)
            return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"Error sending PTO decision email: {e}")
            return False


# Singleton instance
email_service = EmailService()
