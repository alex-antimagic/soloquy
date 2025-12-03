"""
Outlook Integration (MCP)
Supports both workspace-level (shared) and user-level (personal) Outlook accounts
Uses Model Context Protocol via outlook-mcp
"""
from flask import render_template, redirect, url_for, flash, request, session, g, jsonify
from flask_login import login_required, current_user
from app import db, limiter
from app.blueprints.integrations import integrations_bp
from app.models.integration import Integration
from msal import ConfidentialClientApplication
import requests


# Outlook OAuth Scopes (read/send emails, manage calendar)
OUTLOOK_SCOPES = [
    'https://graph.microsoft.com/Mail.ReadWrite',
    'https://graph.microsoft.com/Mail.Send',
    'https://graph.microsoft.com/Calendars.ReadWrite',
    'offline_access'
]


@integrations_bp.route('/outlook/configure', methods=['GET', 'POST'])
@login_required
def outlook_configure():
    """
    Configure Outlook OAuth credentials (workspace only)

    Personal Outlook integrations use workspace credentials automatically.
    Users should use the "Connect" button from the integrations page.

    Query params:
    - scope: Must be 'workspace' (user scope not supported here)
    - for_user_id: Not used (personal connections go through /outlook/connect directly)
    """
    # Only workspace scope is allowed on this page
    scope = request.args.get('scope', 'workspace')
    for_user_id = request.args.get('for_user_id', type=int)

    # Block user scope - they should use /outlook/connect directly
    if scope == 'user':
        from flask import abort
        abort(404)  # This page doesn't exist for user scope

    # Get current user's role
    role = current_user.get_role_in_tenant(g.current_tenant.id)
    is_admin = role in ['owner', 'admin']

    # Workspace scope requires admin
    if not is_admin:
        flash('Only workspace owners and admins can configure workspace integrations.', 'danger')
        return redirect(url_for('integrations.index'))

    # Workspace scope only
    owner_type = 'tenant'
    owner_id = g.current_tenant.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        azure_tenant_id = request.form.get('azure_tenant_id', '').strip()

        if not client_id or not client_secret:
            flash('Please provide both Client ID and Client Secret.', 'danger')
            return redirect(url_for('integrations.outlook_configure'))

        if not azure_tenant_id:
            flash('Please provide your Azure AD Tenant ID or domain.', 'danger')
            return redirect(url_for('integrations.outlook_configure'))

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
        integration.azure_tenant_id = azure_tenant_id

        # Generate display name for workspace
        integration.display_name = display_name or f"{g.current_tenant.name} Outlook"

        # Build redirect URI - single URI for both workspace and user flows
        # Scope is stored in session, not in URL
        integration.redirect_uri = url_for(
            'integrations.outlook_callback',
            _external=True
        )

        db.session.commit()

        flash('Outlook credentials saved! Now authorize access to Outlook account.', 'success')
        return redirect(url_for('integrations.outlook_connect', scope='workspace'))

    return render_template(
        'integrations/outlook_configure.html',
        title='Configure Outlook',
        integration=integration,
        scope='workspace',
        is_workspace=True,
        for_user_id=None,
        target_user=None,
        tenant_integration=None
    )


@integrations_bp.route('/outlook/connect')
@login_required
@limiter.limit("10 per minute")
def outlook_connect():
    """
    Initiate OAuth flow for Outlook

    SECURITY: Rate limited to prevent OAuth flow spam/abuse

    Query params:
    - scope: 'workspace' or 'user'
    - for_user_id: User ID to help (admin only, requires scope='user')
    """
    scope = request.args.get('scope', 'workspace')
    for_user_id = request.args.get('for_user_id', type=int)

    # Get current user's role
    role = current_user.get_role_in_tenant(g.current_tenant.id)
    is_admin = role in ['owner', 'admin']

    # Workspace scope requires admin
    if scope == 'workspace':
        if not is_admin:
            flash('Only workspace owners and admins can connect workspace integrations.', 'danger')
            return redirect(url_for('integrations.index'))

    # Admin-assisted user setup
    if for_user_id:
        # Only admins can help other users
        if not is_admin:
            flash('Only admins can set up integrations for other users.', 'danger')
            return redirect(url_for('integrations.index'))

        # Verify target user is in the same workspace
        from app.models.user import User
        target_user = User.query.get(for_user_id)
        if not target_user or target_user.get_role_in_tenant(g.current_tenant.id) is None:
            flash('User not found in this workspace.', 'danger')
            return redirect(url_for('integrations.index'))

    # Determine owner_type and owner_id
    owner_type = 'tenant' if scope == 'workspace' else 'user'
    if scope == 'workspace':
        owner_id = g.current_tenant.id
    elif for_user_id:
        owner_id = for_user_id  # Admin helping this user
    else:
        owner_id = current_user.id  # User setting up their own

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='outlook',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    # For user-scope integrations, auto-create using workspace credentials
    if scope == 'user' and not integration:
        tenant_integration = Integration.query.filter_by(
            tenant_id=g.current_tenant.id,
            integration_type='outlook',
            owner_type='tenant',
            owner_id=g.current_tenant.id
        ).first()

        if not tenant_integration or not tenant_integration.client_id or not tenant_integration.client_secret:
            flash('Azure AD credentials not configured for this workspace. Please ask an admin to configure the workspace Outlook integration first.', 'danger')
            return redirect(url_for('integrations.index'))

        # Create user integration using workspace credentials
        from app.models.user import User
        target_user = User.query.get(owner_id)

        integration = Integration(
            tenant_id=g.current_tenant.id,
            integration_type='outlook',
            owner_type='user',
            owner_id=owner_id,
            integration_mode='mcp',
            mcp_server_type='outlook',
            is_active=False,
            client_id=tenant_integration.client_id,
            client_secret=tenant_integration.client_secret,
            azure_tenant_id=tenant_integration.azure_tenant_id,  # Copy from workspace
            display_name=f"{target_user.full_name}'s Outlook" if target_user else "Personal Outlook",
            redirect_uri=url_for('integrations.outlook_callback', _external=True)  # Single URI for all flows
        )
        db.session.add(integration)
        db.session.commit()

    if not integration or not integration.client_id or not integration.client_secret:
        flash('Please configure Outlook credentials first.', 'warning')
        return redirect(url_for('integrations.outlook_configure', scope=scope))

    # Build authorization URL manually to avoid MSAL frozenset issues
    try:
        import urllib.parse

        # Join scopes into space-separated string for OAuth
        scopes_str = ' '.join(OUTLOOK_SCOPES)

        # Build OAuth authorization URL with tenant-specific endpoint
        # Use tenant-specific endpoint instead of /common for single-tenant apps
        tenant_endpoint = integration.azure_tenant_id if integration.azure_tenant_id else 'common'

        auth_params = {
            'client_id': integration.client_id,
            'response_type': 'code',
            'redirect_uri': integration.redirect_uri,
            'scope': scopes_str,
            'response_mode': 'query',
            'prompt': 'consent'  # Force consent to get refresh token
        }

        auth_url = f"https://login.microsoftonline.com/{tenant_endpoint}/oauth2/v2.0/authorize?{urllib.parse.urlencode(auth_params)}"

        # Store scope in session for callback
        session['outlook_oauth_scope'] = scope
        if for_user_id:
            session['outlook_oauth_for_user_id'] = for_user_id

        return redirect(auth_url)

    except Exception as e:
        flash(f'Error initiating OAuth: {str(e)}', 'danger')
        return redirect(url_for('integrations.outlook_configure', scope=scope))


@integrations_bp.route('/outlook/callback')
@login_required
@limiter.limit("20 per minute")
def outlook_callback():
    """
    Handle OAuth callback from Microsoft

    SECURITY: Rate limited to prevent callback abuse

    Query params:
    - code: Authorization code (from Azure)

    Session variables:
    - outlook_oauth_scope: 'workspace' or 'user' (set during /outlook/connect)
    - outlook_oauth_for_user_id: User ID if admin helping another user
    """
    # Get authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error')
        error_description = request.args.get('error_description', 'Unknown error')
        flash(f'Authorization failed: {error} - {error_description}', 'danger')
        return redirect(url_for('integrations.index'))

    # Get scope from session (stored during /outlook/connect)
    scope_type = session.get('outlook_oauth_scope', 'workspace')
    for_user_id = session.get('outlook_oauth_for_user_id')

    # Determine owner_type and owner_id
    owner_type = 'tenant' if scope_type == 'workspace' else 'user'
    if scope_type == 'workspace':
        owner_id = g.current_tenant.id
    elif for_user_id:
        owner_id = for_user_id  # Admin helped this user
    else:
        owner_id = current_user.id  # User set up their own

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
        # Exchange code for tokens manually (avoiding MSAL frozenset bug)
        # Use tenant-specific endpoint instead of /common for single-tenant apps
        tenant_endpoint = integration.azure_tenant_id if integration.azure_tenant_id else 'common'
        token_url = f'https://login.microsoftonline.com/{tenant_endpoint}/oauth2/v2.0/token'

        token_data = {
            'client_id': integration.client_id,
            'client_secret': integration.client_secret,
            'code': code,
            'redirect_uri': integration.redirect_uri,
            'grant_type': 'authorization_code',
            'scope': ' '.join(OUTLOOK_SCOPES)
        }

        token_response = requests.post(token_url, data=token_data)
        result = token_response.json()

        if 'error' in result or token_response.status_code != 200:
            error_desc = result.get('error_description', result.get('error', 'Unknown error'))
            flash(f"Error acquiring token: {error_desc}", 'danger')
            return redirect(url_for('integrations.outlook_configure', scope=scope_type))

        # Store tokens with expiry time
        integration.update_tokens(
            access_token=result['access_token'],
            refresh_token=result.get('refresh_token'),
            expires_in=result.get('expires_in', 3600)  # Default to 1 hour
        )
        integration.is_active = True

        success = True

        # Generate appropriate success message
        if for_user_id:
            from app.models.user import User
            target_user = User.query.get(for_user_id)
            message = f"Outlook connected successfully for {target_user.full_name}!"
        else:
            message = "Outlook connected successfully!"

        db.session.commit()
        flash(message, 'success')

        # Clear session
        session.pop('outlook_oauth_scope', None)
        session.pop('outlook_oauth_for_user_id', None)

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

    return jsonify({
        'integration': {
            'id': integration.id,
            'display_name': integration.display_name,
            'is_active': integration.is_active,
            'owner_type': integration.owner_type
        },
        'server': {'status': 'active' if integration.is_active else 'inactive'}
    })


@integrations_bp.route('/outlook/health')
@login_required
def outlook_health():
    """
    Health check for Outlook integration - verifies connectivity and token validity

    Query params:
    - scope: 'workspace' or 'user'

    Returns:
    JSON with health status and details
    """
    from app.services.outlook_service import OutlookGraphService

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
        return jsonify({
            'healthy': False,
            'error': 'Integration not found'
        }), 404

    if not integration.is_active:
        return jsonify({
            'healthy': False,
            'error': 'Integration is not active'
        }), 200

    health_info = {
        'healthy': True,
        'integration_id': integration.id,
        'display_name': integration.display_name,
        'checks': {}
    }

    # Check 1: Token presence
    if not integration.access_token:
        health_info['healthy'] = False
        health_info['checks']['token_present'] = False
        health_info['error'] = 'No access token found'
        return jsonify(health_info), 200

    health_info['checks']['token_present'] = True

    # Check 2: Token expiry
    if integration.token_expires_at:
        from datetime import datetime
        time_until_expiry = (integration.token_expires_at - datetime.utcnow()).total_seconds()
        health_info['checks']['token_expires_in_seconds'] = int(time_until_expiry)
        health_info['checks']['token_needs_refresh'] = integration.needs_refresh()
    else:
        health_info['checks']['token_expires_in_seconds'] = None
        health_info['checks']['token_needs_refresh'] = None

    # Check 3: Refresh if needed
    if integration.needs_refresh():
        try:
            OutlookGraphService.refresh_access_token(integration)
            health_info['checks']['token_refreshed'] = True
        except Exception as e:
            health_info['healthy'] = False
            health_info['checks']['token_refreshed'] = False
            health_info['error'] = f'Token refresh failed: {str(e)}'
            return jsonify(health_info), 200

    # Check 4: Test API connectivity
    try:
        outlook = OutlookGraphService(integration.access_token, integration=integration)
        # Try to list 1 email to verify connectivity
        outlook.list_emails(max_results=1)
        health_info['checks']['api_connectivity'] = True
    except Exception as e:
        health_info['healthy'] = False
        health_info['checks']['api_connectivity'] = False
        health_info['error'] = f'API connectivity test failed: {str(e)}'
        return jsonify(health_info), 200

    return jsonify(health_info), 200
