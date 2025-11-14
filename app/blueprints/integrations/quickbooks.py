"""
QuickBooks Integration Routes
Handles OAuth flow and QuickBooks connection management
"""
from flask import request, redirect, url_for, flash, jsonify, session, g, render_template
from flask_login import login_required, current_user
from app.blueprints.integrations import integrations_bp
from app.services.quickbooks_service import quickbooks_service
from app.models.integration import Integration
from app import db


@integrations_bp.route('/quickbooks/configure', methods=['GET', 'POST'])
@login_required
def quickbooks_configure():
    """Configure QuickBooks OAuth credentials for this tenant"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Check if user is admin
    if not current_user.is_admin(g.current_tenant.id):
        flash('Only workspace administrators can configure integrations.', 'danger')
        return redirect(url_for('integrations.index'))

    # Get or create integration record
    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='quickbooks'
    ).first()

    if request.method == 'POST':
        try:
            client_id = request.form.get('client_id', '').strip()
            client_secret = request.form.get('client_secret', '').strip()
            redirect_uri = request.form.get('redirect_uri', '').strip()
            environment = request.form.get('environment', 'sandbox')

            # Validate inputs
            if not client_id or not client_secret:
                flash('Client ID and Client Secret are required.', 'danger')
                return render_template('integrations/quickbooks_configure.html',
                                     integration=integration)

            # Default redirect URI if not provided
            if not redirect_uri:
                redirect_uri = url_for('integrations.quickbooks_callback', _external=True)

            if not integration:
                # Create new integration
                integration = Integration(
                    tenant_id=g.current_tenant.id,
                    integration_type='quickbooks'
                )
                db.session.add(integration)

            # Update credentials
            integration.client_id = client_id
            integration.client_secret = client_secret
            integration.redirect_uri = redirect_uri
            integration.environment = environment

            db.session.commit()

            flash('QuickBooks credentials saved successfully! You can now connect.', 'success')
            return redirect(url_for('integrations.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error saving credentials: {str(e)}', 'danger')

    return render_template('integrations/quickbooks_configure.html',
                         integration=integration)


@integrations_bp.route('/quickbooks/connect')
@login_required
def quickbooks_connect():
    """Initiate QuickBooks OAuth flow"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    try:
        # Get integration record to retrieve OAuth credentials
        integration = Integration.query.filter_by(
            tenant_id=g.current_tenant.id,
            integration_type='quickbooks'
        ).first()

        if not integration or not integration.client_id or not integration.client_secret:
            flash('Please configure your QuickBooks OAuth credentials first.', 'warning')
            return redirect(url_for('integrations.quickbooks_configure'))

        auth_url, state_token = quickbooks_service.get_authorization_url(integration)

        # Store state token in session for verification
        session['qb_state_token'] = state_token
        session['qb_tenant_id'] = g.current_tenant.id

        # Redirect to QuickBooks authorization
        return redirect(auth_url)

    except Exception as e:
        flash(f'Error connecting to QuickBooks: {str(e)}', 'danger')
        return redirect(url_for('integrations.index'))


@integrations_bp.route('/quickbooks/callback')
@login_required
def quickbooks_callback():
    """Handle QuickBooks OAuth callback"""
    # Get authorization code and realm ID from callback
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')
    state = request.args.get('state')
    error = request.args.get('error')

    # Check for errors
    if error:
        flash(f'QuickBooks authorization failed: {error}', 'danger')
        return redirect(url_for('integrations.index'))

    if not auth_code or not realm_id:
        flash('Invalid QuickBooks callback parameters.', 'danger')
        return redirect(url_for('integrations.index'))

    # Verify state token
    stored_state = session.get('qb_state_token')
    tenant_id = session.get('qb_tenant_id')

    if not stored_state or state != stored_state:
        flash('Invalid state token. Please try connecting again.', 'danger')
        return redirect(url_for('integrations.index'))

    if tenant_id != g.current_tenant.id:
        flash('Tenant mismatch. Please try connecting again.', 'danger')
        return redirect(url_for('integrations.index'))

    try:
        # Get integration record (should already exist with credentials from configure step)
        integration = Integration.query.filter_by(
            tenant_id=g.current_tenant.id,
            integration_type='quickbooks'
        ).first()

        if not integration or not integration.client_id or not integration.client_secret:
            flash('QuickBooks credentials not found. Please configure first.', 'danger')
            return redirect(url_for('integrations.quickbooks_configure'))

        # Exchange code for tokens
        tokens = quickbooks_service.exchange_code_for_tokens(
            integration,
            auth_code,
            realm_id,
            stored_state
        )

        # Update integration with tokens and company ID
        integration.update_tokens(tokens['access_token'], tokens['refresh_token'])
        integration.company_id = tokens['company_id']
        integration.is_active = True
        message = 'QuickBooks connected successfully!'

        db.session.commit()

        # Get company info to display
        company_info = quickbooks_service.get_company_info(integration)
        if company_info:
            flash(f'{message} Connected to: {company_info["company_name"]}', 'success')
        else:
            flash(message, 'success')

        # Clear session data
        session.pop('qb_state_token', None)
        session.pop('qb_tenant_id', None)

        return redirect(url_for('integrations.index'))

    except Exception as e:
        flash(f'Error connecting to QuickBooks: {str(e)}', 'danger')
        return redirect(url_for('integrations.index'))


@integrations_bp.route('/quickbooks/disconnect', methods=['POST'])
@login_required
def quickbooks_disconnect():
    """Disconnect QuickBooks integration"""
    if not g.current_tenant:
        return jsonify({'error': 'No active workspace'}), 400

    try:
        integration = Integration.query.filter_by(
            tenant_id=g.current_tenant.id,
            integration_type='quickbooks',
            is_active=True
        ).first()

        if not integration:
            return jsonify({'error': 'QuickBooks not connected'}), 404

        # Deactivate integration
        integration.deactivate()
        db.session.commit()

        flash('QuickBooks disconnected successfully.', 'success')
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@integrations_bp.route('/quickbooks/status')
@login_required
def quickbooks_status():
    """Get QuickBooks connection status"""
    if not g.current_tenant:
        return jsonify({'connected': False})

    integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='quickbooks',
        is_active=True
    ).first()

    if not integration:
        return jsonify({'connected': False})

    try:
        # Get company info to verify connection is working
        company_info = quickbooks_service.get_company_info(integration)

        return jsonify({
            'connected': True,
            'company_name': company_info['company_name'] if company_info else None,
            'company_id': integration.company_id,
            'connected_at': integration.connected_at.isoformat() if integration.connected_at else None,
            'last_sync': integration.last_sync_at.isoformat() if integration.last_sync_at else None
        })

    except Exception as e:
        return jsonify({
            'connected': True,
            'error': str(e),
            'company_id': integration.company_id
        })
