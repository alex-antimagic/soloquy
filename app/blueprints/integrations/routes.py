from flask import render_template, g
from flask_login import login_required
from app.blueprints.integrations import integrations_bp
from app.models.integration import Integration

@integrations_bp.route('/')
@login_required
def index():
    """Integrations management page"""

    # Check QuickBooks connection status
    qb_integration = None
    if g.current_tenant:
        qb_integration = Integration.query.filter_by(
            tenant_id=g.current_tenant.id,
            integration_type='quickbooks',
            is_active=True
        ).first()

    # Define available integrations with their status
    integrations = [
        {
            'name': 'QuickBooks Online',
            'description': 'Sync your accounting and financial data',
            'logo': 'quickbooks.svg',
            'category': 'Accounting',
            'available': True,
            'connected': qb_integration is not None,
            'connect_url': 'integrations.quickbooks_connect' if not qb_integration else None,
            'status_url': 'integrations.quickbooks_status',
            'disconnect_url': 'integrations.quickbooks_disconnect' if qb_integration else None
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
