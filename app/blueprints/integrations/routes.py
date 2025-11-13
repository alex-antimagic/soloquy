from flask import render_template
from flask_login import login_required
from app.blueprints.integrations import integrations_bp

@integrations_bp.route('/')
@login_required
def index():
    """Integrations management page"""

    # Define available integrations with their status
    integrations = [
        {
            'name': 'QuickBooks Online',
            'description': 'Sync your accounting and financial data',
            'logo': 'quickbooks.svg',
            'category': 'Accounting',
            'available': False
        },
        {
            'name': 'Salesforce',
            'description': 'Connect your CRM and sales pipeline',
            'logo': 'salesforce.svg',
            'category': 'CRM',
            'available': False
        },
        {
            'name': 'Stripe',
            'description': 'Process payments and manage subscriptions',
            'logo': 'stripe.svg',
            'category': 'Payments',
            'available': False
        },
        {
            'name': 'Slack',
            'description': 'Send notifications to your Slack workspace',
            'logo': 'slack.svg',
            'category': 'Communication',
            'available': False
        },
        {
            'name': 'Mailchimp',
            'description': 'Manage email campaigns and marketing automation',
            'logo': 'mailchimp.svg',
            'category': 'Marketing',
            'available': False
        },
        {
            'name': 'Zendesk',
            'description': 'Integrate support tickets and customer service',
            'logo': 'zendesk.svg',
            'category': 'Support',
            'available': False
        },
        {
            'name': 'Google Workspace',
            'description': 'Connect Gmail, Calendar, and Drive',
            'logo': 'google-workspace.svg',
            'category': 'Productivity',
            'available': False
        },
        {
            'name': 'Microsoft 365',
            'description': 'Integrate Outlook, Teams, and OneDrive',
            'logo': 'microsoft-365.svg',
            'category': 'Productivity',
            'available': False
        }
    ]

    return render_template('integrations/index.html',
                         title='Integrations',
                         integrations=integrations)
