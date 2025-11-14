"""
Outlook Integration (MCP)
Supports both workspace-level (shared) and user-level (personal) Outlook accounts
Uses Model Context Protocol via outlook-mcp
"""
from flask import render_template, redirect, url_for, flash, request, session, g, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.integrations import integrations_bp
from app.models.integration import Integration
from app.services.mcp_manager import mcp_manager
from msal import ConfidentialClientApplication
import requests


# Outlook OAuth Scopes (read/send emails, manage folders)
OUTLOOK_SCOPES = [
    'https://graph.microsoft.com/Mail.ReadWrite',
    'https://graph.microsoft.com/Mail.Send',
    'offline_access'
]


@integrations_bp.route('/outlook/configure', methods=['GET', 'POST'])
@login_required
def outlook_configure():
    """
    Configure Outlook OAuth credentials

    Supports two modes:
    - workspace: Shared Outlook account for entire workspace (admin only)
    - user: Personal Outlook account for individual user

    Query params:
    - scope: 'workspace' or 'user' (default: 'workspace')
    """
    # Check scope (workspace or user)
    scope = request.args.get('scope', 'workspace')

    # Workspace scope requires admin
    if scope == 'workspace':
        role = current_user.get_role_in_tenant(g.current_tenant.id)
        if role not in ['owner', 'admin']:
            flash('Only workspace owners and admins can configure workspace integrations.', 'danger')
            return redirect(url_for('integrations.index'))

    # Check if integration already exists
    owner_type = 'tenant' if scope == 'workspace' else 'user'
    owner_id = g.current_tenant.id if scope == 'workspace' else current_user.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if request.method == 'POST':
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        display_name = request.form.get('display_name', '').strip()

        if not client_id or not client_secret:
            flash('Please provide both Client ID and Client Secret.', 'danger')
            return redirect(url_for('integrations.outlook_configure', scope=scope))

        # Create or update integration
        if not integration:
            integration = Integration(
                tenant_id=g.current_tenant.id,
                integration_type='outlook',
                owner_type=owner_type,
                owner_id=owner_id,
                integration_mode='mcp',
                mcp_server_type='outlook',
                is_active=False  # Not active until OAuth completes
            )
            db.session.add(integration)

        # Set credentials and display name
        integration.client_id = client_id
        integration.client_secret = client_secret
        integration.display_name = display_name or (
            f"{g.current_tenant.name} Outlook" if scope == 'workspace'
            else f"{current_user.full_name}'s Outlook"
        )

        # Build redirect URI
        integration.redirect_uri = url_for(
            'integrations.outlook_callback',
            scope=scope,
            _external=True
        )

        db.session.commit()

        flash('Outlook credentials saved! Now authorize access to your Outlook account.', 'success')
        return redirect(url_for('integrations.outlook_connect', scope=scope))

    return render_template(
        'integrations/outlook_configure.html',
        title='Configure Outlook',
        integration=integration,
        scope=scope,
        is_workspace=scope == 'workspace'
    )


@integrations_bp.route('/outlook/connect')
@login_required
def outlook_connect():
    """
    Initiate OAuth flow for Outlook

    Query params:
    - scope: 'workspace' or 'user'
    """
    scope = request.args.get('scope', 'workspace')

    # Workspace scope requires admin
    if scope == 'workspace':
        role = current_user.get_role_in_tenant(g.current_tenant.id)
        if role not in ['owner', 'admin']:
            flash('Only workspace owners and admins can connect workspace integrations.', 'danger')
            return redirect(url_for('integrations.index'))

    # Get integration
    owner_type = 'tenant' if scope == 'workspace' else 'user'
    owner_id = g.current_tenant.id if scope == 'workspace' else current_user.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if not integration or not integration.client_id or not integration.client_secret:
        flash('Please configure Outlook credentials first.', 'warning')
        return redirect(url_for('integrations.outlook_configure', scope=scope))

    # Create MSAL app
    try:
        msal_app = ConfidentialClientApplication(
            integration.client_id,
            authority='https://login.microsoftonline.com/common',
            client_credential=integration.client_secret
        )

        # Build authorization URL
        auth_url = msal_app.get_authorization_request_url(
            scopes=OUTLOOK_SCOPES,
            redirect_uri=integration.redirect_uri,
            prompt='consent'  # Force consent to get refresh token
        )

        # Store scope in session
        session['outlook_oauth_scope'] = scope

        return redirect(auth_url)

    except Exception as e:
        flash(f'Error initiating OAuth: {str(e)}', 'danger')
        return redirect(url_for('integrations.outlook_configure', scope=scope))


@integrations_bp.route('/outlook/callback')
@login_required
def outlook_callback():
    """
    Handle OAuth callback from Microsoft

    Query params:
    - code: Authorization code
    - scope: 'workspace' or 'user'
    """
    # Get authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error')
        error_description = request.args.get('error_description', 'Unknown error')
        flash(f'Authorization failed: {error} - {error_description}', 'danger')
        return redirect(url_for('integrations.index'))

    scope_type = session.get('outlook_oauth_scope', 'workspace')

    # Get integration
    owner_type = 'tenant' if scope_type == 'workspace' else 'user'
    owner_id = g.current_tenant.id if scope_type == 'workspace' else current_user.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if not integration:
        flash('Integration not found. Please configure again.', 'danger')
        return redirect(url_for('integrations.outlook_configure', scope=scope_type))

    try:
        # Exchange code for tokens using MSAL
        msal_app = ConfidentialClientApplication(
            integration.client_id,
            authority='https://login.microsoftonline.com/common',
            client_credential=integration.client_secret
        )

        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=OUTLOOK_SCOPES,
            redirect_uri=integration.redirect_uri
        )

        if 'error' in result:
            flash(f"Error acquiring token: {result.get('error_description', 'Unknown error')}", 'danger')
            return redirect(url_for('integrations.outlook_configure', scope=scope_type))

        # Store tokens
        integration.access_token = result['access_token']
        integration.refresh_token = result.get('refresh_token')
        integration.is_active = True

        # Write credentials to filesystem for MCP server
        creds_data = {
            'client_id': integration.client_id,
            'client_secret': integration.client_secret,
            'access_token': result['access_token'],
            'refresh_token': result.get('refresh_token'),
            'expires_at': result.get('expires_in')  # Seconds until expiration
        }

        mcp_manager.write_credentials(integration, creds_data)

        # Start MCP server
        success, message = mcp_manager.start_mcp_server(integration)

        if success:
            db.session.commit()
            flash(f'Outlook connected successfully! {message}', 'success')
        else:
            flash(f'Outlook connected but MCP server failed to start: {message}', 'warning')
            db.session.commit()

        # Clear session
        session.pop('outlook_oauth_scope', None)

        return redirect(url_for('integrations.index'))

    except Exception as e:
        flash(f'Error completing OAuth: {str(e)}', 'danger')
        return redirect(url_for('integrations.outlook_configure', scope=scope_type))


@integrations_bp.route('/outlook/disconnect', methods=['POST'])
@login_required
def outlook_disconnect():
    """
    Disconnect Outlook integration

    Form data:
    - scope: 'workspace' or 'user'
    """
    scope = request.form.get('scope', 'workspace')

    # Workspace scope requires admin
    if scope == 'workspace':
        role = current_user.get_role_in_tenant(g.current_tenant.id)
        if role not in ['owner', 'admin']:
            flash('Only workspace owners and admins can disconnect workspace integrations.', 'danger')
            return redirect(url_for('integrations.index'))

    # Get integration
    owner_type = 'tenant' if scope == 'workspace' else 'user'
    owner_id = g.current_tenant.id if scope == 'workspace' else current_user.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if not integration:
        flash('Integration not found.', 'warning')
        return redirect(url_for('integrations.index'))

    try:
        # Stop MCP server
        mcp_manager.stop_mcp_server(integration)

        # Cleanup credentials
        mcp_manager.cleanup_credentials(integration)

        # Deactivate integration
        integration.deactivate()
        db.session.commit()

        flash('Outlook disconnected successfully.', 'success')

    except Exception as e:
        flash(f'Error disconnecting Outlook: {str(e)}', 'danger')

    return redirect(url_for('integrations.index'))


@integrations_bp.route('/outlook/status')
@login_required
def outlook_status():
    """
    Get Outlook MCP server status

    Query params:
    - scope: 'workspace' or 'user'

    Returns:
    JSON with server status
    """
    scope = request.args.get('scope', 'workspace')

    # Get integration
    owner_type = 'tenant' if scope == 'workspace' else 'user'
    owner_id = g.current_tenant.id if scope == 'workspace' else current_user.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if not integration:
        return jsonify({'error': 'Integration not found'}), 404

    status = mcp_manager.get_process_status(integration)

    return jsonify({
        'integration': {
            'id': integration.id,
            'display_name': integration.display_name,
            'is_active': integration.is_active,
            'owner_type': integration.owner_type
        },
        'server': status
    })
