"""
Email Service
Sends emails using Twilio SendGrid
"""
import os
from flask import url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class EmailService:
    """Service for sending emails via Twilio SendGrid"""

    def __init__(self):
        """Initialize SendGrid client"""
        self.api_key = os.environ.get('SENDGRID_API_KEY')
        self.from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@soloquy.app')
        self.from_name = os.environ.get('SENDGRID_FROM_NAME', 'Soloquy')

        if not self.api_key:
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
            subject = f"{inviter_name} invited you to join {workspace_name} on Soloquy"

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
            <p>Join your team on Soloquy</p>
        </div>

        <div class="content">
            <p>Hi there,</p>

            <p><strong>{inviter_name}</strong> has invited you to join their workspace on Soloquy.</p>

            <div class="workspace-info">
                <strong>Workspace:</strong> {workspace_name}<br>
                <strong>Role:</strong> {invitation.role.title()}
            </div>

            <p>Soloquy is an AI-powered workspace platform that helps teams collaborate with intelligent AI agents.</p>

            <center>
                <a href="{invitation_url}" class="cta-button">Accept Invitation</a>
            </center>

            <p style="font-size: 14px; color: #666; margin-top: 30px;">
                This invitation will expire in 7 days. If you have any questions, please contact {inviter_name}.
            </p>
        </div>

        <div class="footer">
            <p>This email was sent by Soloquy</p>
            <p><a href="https://soloquy.app">Visit Soloquy</a></p>
        </div>
    </div>
</body>
</html>
            """

            # Plain text fallback
            text_content = f"""
You're invited to join {workspace_name} on Soloquy!

{inviter_name} has invited you to join their workspace as a {invitation.role}.

Accept your invitation here:
{invitation_url}

This invitation will expire in 7 days.

---
Soloquy - AI for everyone
            """

            # Create SendGrid message
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
            subject = "Welcome to Soloquy!"

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
            <h1>Welcome to Soloquy!</h1>
        </div>

        <div class="content">
            <p>Hi {user.first_name or 'there'},</p>

            <p>Welcome to Soloquy - AI for everyone!</p>

            <p>Your account has been created successfully. You can now create workspaces, invite team members, and collaborate with intelligent AI agents.</p>

            <p>If you have any questions or need help getting started, don't hesitate to reach out.</p>

            <p>Best regards,<br>The Soloquy Team</p>
        </div>

        <div class="footer">
            <p>This email was sent by Soloquy</p>
        </div>
    </div>
</body>
</html>
            """

            text_content = f"""
Welcome to Soloquy!

Hi {user.first_name or 'there'},

Welcome to Soloquy - AI for everyone!

Your account has been created successfully. You can now create workspaces, invite team members, and collaborate with intelligent AI agents.

If you have any questions or need help getting started, don't hesitate to reach out.

Best regards,
The Soloquy Team
            """

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


# Singleton instance
email_service = EmailService()
