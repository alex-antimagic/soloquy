from flask import render_template, g, current_app
from flask_login import login_required, current_user
from app.blueprints.integrations import integrations_bp
from app.models.integration import Integration

@integrations_bp.route('/')
@login_required
def index():
    """Integrations management page"""

    # Check user's role for admin-only features
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    is_admin = user_role in ['owner', 'admin']

    # Check QuickBooks connection status (workspace-level only)
    qb_integration = None
    qb_configured = False
    if g.current_tenant:
        qb_integration = Integration.query.filter_by(
            tenant_id=g.current_tenant.id,
            integration_type='quickbooks'
        ).first()

        # Check if OAuth credentials are configured
        if qb_integration:
            qb_configured = bool(qb_integration.client_id and qb_integration.client_secret)

    # Check MCP integrations (both workspace and personal)
    # Gmail - Workspace
    gmail_workspace = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='gmail',
        owner_type='tenant',
        owner_id=g.current_tenant.id
    ).first()

    # Gmail - Personal
    gmail_personal = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='gmail',
        owner_type='user',
        owner_id=current_user.id
    ).first()

    # Outlook - Workspace
    outlook_workspace = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type='tenant',
        owner_id=g.current_tenant.id
    ).first()

    # Outlook - Personal
    outlook_personal = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type='user',
        owner_id=current_user.id
    ).first()

    # Google Drive - Workspace
    drive_workspace = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='google_drive',
        owner_type='tenant',
        owner_id=g.current_tenant.id
    ).first()

    # Google Drive - Personal
    drive_personal = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='google_drive',
        owner_type='user',
        owner_id=current_user.id
    ).first()

    # Build workspace integrations (admin-only)
    workspace_integrations = []
    if is_admin:
        workspace_integrations = [
            {
                'name': 'QuickBooks Online',
                'description': 'Sync your accounting and financial data',
                'logo': 'quickbooks.svg',
                'category': 'Accounting',
                'available': True,
                'connected': qb_integration is not None and qb_integration.is_active,
                'configured': qb_configured,
                'configure_url': 'integrations.quickbooks_configure',
                'connect_url': 'integrations.quickbooks_connect' if qb_configured else None,
                'status_url': 'integrations.quickbooks_status',
                'disconnect_url': 'integrations.quickbooks_disconnect' if qb_integration and qb_integration.is_active else None
            },
            {
                'name': 'Gmail',
                'description': 'Shared team Gmail account for AI agent access',
                'logo': 'gmail.svg',
                'category': 'Email',
                'available': True,
                'connected': gmail_workspace is not None and gmail_workspace.is_active,
                'configured': gmail_workspace is not None and bool(gmail_workspace.client_id),
                'configure_url': 'integrations.gmail_configure',
                'configure_params': {'scope': 'workspace'},
                'connect_url': 'integrations.gmail_connect' if gmail_workspace and gmail_workspace.client_id else None,
                'connect_params': {'scope': 'workspace'},
                'status_url': 'integrations.gmail_status',
                'status_params': {'scope': 'workspace'},
                'disconnect_url': 'integrations.gmail_disconnect' if gmail_workspace and gmail_workspace.is_active else None,
                'display_name': gmail_workspace.display_name if gmail_workspace else None
            },
            {
                'name': 'Outlook',
                'description': 'Shared team Outlook account for AI agent access',
                'logo': 'outlook.svg',
                'category': 'Email',
                'available': True,
                'connected': outlook_workspace is not None and outlook_workspace.is_active,
                'configured': outlook_workspace is not None and bool(outlook_workspace.client_id),
                'configure_url': 'integrations.outlook_configure',
                'configure_params': {'scope': 'workspace'},
                'connect_url': 'integrations.outlook_connect' if outlook_workspace and outlook_workspace.client_id else None,
                'connect_params': {'scope': 'workspace'},
                'status_url': 'integrations.outlook_status',
                'status_params': {'scope': 'workspace'},
                'disconnect_url': 'integrations.outlook_disconnect' if outlook_workspace and outlook_workspace.is_active else None,
                'display_name': outlook_workspace.display_name if outlook_workspace else None
            },
            {
                'name': 'Google Drive',
                'description': 'Shared team Google Drive for AI agent access',
                'logo': 'google-drive.svg',
                'category': 'Storage',
                'available': True,
                'connected': drive_workspace is not None and drive_workspace.is_active,
                'configured': drive_workspace is not None and bool(drive_workspace.client_id),
                'configure_url': 'integrations.google_drive_configure',
                'configure_params': {'scope': 'workspace'},
                'connect_url': 'integrations.google_drive_connect' if drive_workspace and drive_workspace.client_id else None,
                'connect_params': {'scope': 'workspace'},
                'status_url': 'integrations.google_drive_status',
                'status_params': {'scope': 'workspace'},
                'disconnect_url': 'integrations.google_drive_disconnect' if drive_workspace and drive_workspace.is_active else None,
                'display_name': drive_workspace.display_name if drive_workspace else None
            }
        ]

    # Build personal integrations (available to all users)
    personal_integrations = [
        {
            'name': 'Gmail',
            'description': 'Your personal Gmail account for AI agent access',
            'logo': 'gmail.svg',
            'category': 'Email',
            'available': True,
            'connected': gmail_personal is not None and gmail_personal.is_active,
            'configured': gmail_personal is not None and bool(gmail_personal.client_id),
            'configure_url': 'integrations.gmail_configure',
            'configure_params': {'scope': 'user'},
            'connect_url': 'integrations.gmail_connect' if gmail_personal and gmail_personal.client_id else None,
            'connect_params': {'scope': 'user'},
            'status_url': 'integrations.gmail_status',
            'status_params': {'scope': 'user'},
            'disconnect_url': 'integrations.gmail_disconnect' if gmail_personal and gmail_personal.is_active else None,
            'display_name': gmail_personal.display_name if gmail_personal else None
        },
        {
            'name': 'Outlook',
            'description': 'Your personal Outlook account for AI agent access',
            'logo': 'outlook.svg',
            'category': 'Email',
            'available': True,
            'connected': outlook_personal is not None and outlook_personal.is_active,
            'configured': outlook_personal is not None and bool(outlook_personal.client_id),
            'configure_url': 'integrations.outlook_configure',
            'configure_params': {'scope': 'user'},
            'connect_url': 'integrations.outlook_connect' if outlook_personal and outlook_personal.client_id else None,
            'connect_params': {'scope': 'user'},
            'status_url': 'integrations.outlook_status',
            'status_params': {'scope': 'user'},
            'disconnect_url': 'integrations.outlook_disconnect' if outlook_personal and outlook_personal.is_active else None,
            'display_name': outlook_personal.display_name if outlook_personal else None
        },
        {
            'name': 'Google Drive',
            'description': 'Your personal Google Drive for AI agent access',
            'logo': 'google-drive.svg',
            'category': 'Storage',
            'available': True,
            'connected': drive_personal is not None and drive_personal.is_active,
            'configured': drive_personal is not None and bool(drive_personal.client_id),
            'configure_url': 'integrations.google_drive_configure',
            'configure_params': {'scope': 'user'},
            'connect_url': 'integrations.google_drive_connect' if drive_personal and drive_personal.client_id else None,
            'connect_params': {'scope': 'user'},
            'status_url': 'integrations.google_drive_status',
            'status_params': {'scope': 'user'},
            'disconnect_url': 'integrations.google_drive_disconnect' if drive_personal and drive_personal.is_active else None,
            'display_name': drive_personal.display_name if drive_personal else None
        }
    ]

    # Get workspace members for admin helper UI (admin only)
    workspace_members_with_integrations = []
    if is_admin and g.current_tenant:
        workspace_members = g.current_tenant.get_members()

        for member in workspace_members:
            # Skip current user (they use normal personal integrations UI)
            if member.id == current_user.id:
                continue

            # Check member's personal integrations
            member_gmail = Integration.query.filter_by(
                tenant_id=g.current_tenant.id,
                integration_type='gmail',
                owner_type='user',
                owner_id=member.id
            ).first()

            member_outlook = Integration.query.filter_by(
                tenant_id=g.current_tenant.id,
                integration_type='outlook',
                owner_type='user',
                owner_id=member.id
            ).first()

            member_drive = Integration.query.filter_by(
                tenant_id=g.current_tenant.id,
                integration_type='google_drive',
                owner_type='user',
                owner_id=member.id
            ).first()

            workspace_members_with_integrations.append({
                'user': member,
                'gmail': {
                    'connected': member_gmail is not None and member_gmail.is_active,
                    'configured': member_gmail is not None and bool(member_gmail.client_id)
                },
                'outlook': {
                    'connected': member_outlook is not None and member_outlook.is_active,
                    'configured': member_outlook is not None and bool(member_outlook.client_id)
                },
                'google_drive': {
                    'connected': member_drive is not None and member_drive.is_active,
                    'configured': member_drive is not None and bool(member_drive.client_id)
                }
            })

    return render_template('integrations/index.html',
                         title='Integrations',
                         workspace_integrations=workspace_integrations,
                         personal_integrations=personal_integrations,
                         is_admin=is_admin,
                         workspace_members_with_integrations=workspace_members_with_integrations)
