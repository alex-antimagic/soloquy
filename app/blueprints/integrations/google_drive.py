"""
Google Drive Integration (MCP)
Supports both workspace-level (shared) and user-level (personal) Google Drive accounts
Uses Model Context Protocol via @piotr-agier/google-drive-mcp
"""
from flask import render_template, redirect, url_for, flash, request, session, g, jsonify
from flask_login import login_required, current_user
from app import db, limiter
from app.blueprints.integrations import integrations_bp
from app.models.integration import Integration
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import os


# Google Drive OAuth Scopes (read/write files, manage folders)
GOOGLE_DRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]


@integrations_bp.route('/google-drive/configure', methods=['GET', 'POST'])
@login_required
def google_drive_configure():
    """
    Configure Google Drive OAuth credentials

    Supports two modes:
    - workspace: Shared Google Drive for entire workspace (admin only)
    - user: Personal Google Drive for individual user

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
        integration_type='google_drive',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if request.method == 'POST':
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        display_name = request.form.get('display_name', '').strip()

        if not client_id or not client_secret:
            flash('Please provide both Client ID and Client Secret.', 'danger')
            return redirect(url_for('integrations.google_drive_configure', scope=scope))

        # Create or update integration
        if not integration:
            integration = Integration(
                tenant_id=g.current_tenant.id,
                integration_type='google_drive',
                owner_type=owner_type,
                owner_id=owner_id,
                integration_mode='mcp',
                mcp_server_type='google_drive',
                is_active=False  # Not active until OAuth completes
            )
            db.session.add(integration)

        # Set credentials and display name
        integration.client_id = client_id
        integration.client_secret = client_secret
        integration.display_name = display_name or (
            f"{g.current_tenant.name} Google Drive" if scope == 'workspace'
            else f"{current_user.full_name}'s Google Drive"
        )

        # Build redirect URI
        integration.redirect_uri = url_for(
            'integrations.google_drive_callback',
            scope=scope,
            _external=True
        )

        db.session.commit()

        flash('Google Drive credentials saved! Now authorize access to your Google Drive.', 'success')
        return redirect(url_for('integrations.google_drive_connect', scope=scope))

    return render_template(
        'integrations/google_drive_configure.html',
        title='Configure Google Drive',
        integration=integration,
        scope=scope,
        is_workspace=scope == 'workspace'
    )


@integrations_bp.route('/google-drive/connect')
@login_required
@limiter.limit("10 per minute")
def google_drive_connect():
    """
    Initiate OAuth flow for Google Drive

    SECURITY: Rate limited to prevent OAuth flow spam/abuse

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
        integration_type='google_drive',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if not integration or not integration.client_id or not integration.client_secret:
        flash('Please configure Google Drive credentials first.', 'warning')
        return redirect(url_for('integrations.google_drive_configure', scope=scope))

    # Create OAuth flow
    try:
        client_config = {
            "web": {
                "client_id": integration.client_id,
                "client_secret": integration.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [integration.redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_DRIVE_SCOPES,
            redirect_uri=integration.redirect_uri
        )

        # Store state in session
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to get refresh token
        )

        session['google_drive_oauth_state'] = state
        session['google_drive_oauth_scope'] = scope

        return redirect(authorization_url)

    except Exception as e:
        flash(f'Error initiating OAuth: {str(e)}', 'danger')
        return redirect(url_for('integrations.google_drive_configure', scope=scope))


@integrations_bp.route('/google-drive/callback/<scope>')
@login_required
@limiter.limit("20 per minute")
def google_drive_callback(scope):
    """
    Handle OAuth callback from Google

    SECURITY: Rate limited to prevent callback abuse

    Path params:
    - scope: 'workspace' or 'user'

    Query params:
    - state: OAuth state token (from Google)
    - code: Authorization code (from Google)
    """
    # Verify state
    state = request.args.get('state')
    stored_state = session.get('google_drive_oauth_state')
    scope_type = scope

    if not state or state != stored_state:
        flash('Invalid OAuth state. Please try again.', 'danger')
        return redirect(url_for('integrations.index'))

    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('Authorization denied or failed.', 'danger')
        return redirect(url_for('integrations.index'))

    # Get integration
    owner_type = 'tenant' if scope_type == 'workspace' else 'user'
    owner_id = g.current_tenant.id if scope_type == 'workspace' else current_user.id

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='google_drive',
        owner_type=owner_type,
        owner_id=owner_id
    ).first()

    if not integration:
        flash('Integration not found. Please configure again.', 'danger')
        return redirect(url_for('integrations.google_drive_configure', scope=scope_type))

    try:
        # Exchange code for tokens
        client_config = {
            "web": {
                "client_id": integration.client_id,
                "client_secret": integration.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [integration.redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_DRIVE_SCOPES,
            redirect_uri=integration.redirect_uri,
            state=state
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Store tokens
        integration.access_token = credentials.token
        integration.refresh_token = credentials.refresh_token
        integration.is_active = True

        success = True
        message = "Connected successfully"

        db.session.commit()
        flash(f'Google Drive connected successfully! {message}', 'success')

        # Clear session
        session.pop('google_drive_oauth_state', None)
        session.pop('google_drive_oauth_scope', None)

        return redirect(url_for('integrations.index'))

    except Exception as e:
        flash(f'Error completing OAuth: {str(e)}', 'danger')
        return redirect(url_for('integrations.google_drive_configure', scope=scope_type))


@integrations_bp.route('/google-drive/disconnect', methods=['POST'])
@login_required
def google_drive_disconnect():
    """
    Disconnect Google Drive integration

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
        integration_type='google_drive',
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

        flash('Google Drive disconnected successfully.', 'success')

    except Exception as e:
        flash(f'Error disconnecting Google Drive: {str(e)}', 'danger')

    return redirect(url_for('integrations.index'))


@integrations_bp.route('/google-drive/status')
@login_required
def google_drive_status():
    """
    Get Google Drive MCP server status

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
        integration_type='google_drive',
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
