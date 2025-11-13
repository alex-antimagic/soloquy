from flask import render_template, redirect, url_for, flash, request, session, g, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.tenant import tenant_bp
from app.blueprints.tenant.forms import InviteUserForm, WorkspaceContextForm
from app.models.tenant import Tenant, TenantMembership
from app.models.department import Department
from app.models.user import User
from app.services.default_departments import create_default_departments
from app.services.applet_manager import initialize_applets_for_tenant


@tenant_bp.route('/')
@login_required
def home():
    """Main dashboard - shows current tenant overview"""
    # Get user's tenants
    tenants = current_user.get_tenants()

    # If user has no workspaces, redirect to wizard
    if not tenants:
        return redirect(url_for('tenant.wizard'))

    # If no current tenant is selected, select the first one
    if not g.current_tenant and tenants:
        session['current_tenant_id'] = tenants[0].id
        g.current_tenant = tenants[0]

    # Get departments for current tenant
    departments = []
    if g.current_tenant:
        departments = g.current_tenant.get_departments()

    return render_template('tenant/dashboard.html',
                           title='Dashboard',
                           tenants=tenants,
                           departments=departments)


@tenant_bp.route('/switch/<int:tenant_id>')
@login_required
def switch_tenant(tenant_id):
    """Switch to a different tenant"""
    # Verify user has access to this tenant
    if current_user.has_tenant_access(tenant_id):
        session['current_tenant_id'] = tenant_id
        flash('Switched tenant successfully.', 'success')
    else:
        flash('You do not have access to this tenant.', 'danger')

    return redirect(url_for('tenant.home'))


@tenant_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new tenant"""
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug', '').lower().replace(' ', '-')
        description = request.form.get('description')
        website_url = request.form.get('website_url', '').strip()
        company_size = request.form.get('company_size')
        template = request.form.get('template', 'business')  # Default to business template

        # Get custom configuration if custom template
        selected_departments = request.form.getlist('departments') if template == 'custom' else None
        selected_applets = request.form.getlist('applets') if template == 'custom' else None

        # Normalize website URL - add https:// if missing
        if website_url:
            # Remove any existing protocol
            website_url = website_url.replace('http://', '').replace('https://', '')
            # Add https:// protocol
            website_url = f'https://{website_url}'

        # Determine initial scraping status
        scraping_status = 'pending' if website_url else 'skipped'

        # Create tenant
        tenant = Tenant(
            name=name,
            slug=slug,
            description=description,
            website_url=website_url,
            company_size=company_size if company_size else None,
            context_scraping_status=scraping_status
        )
        db.session.add(tenant)
        db.session.flush()  # Get tenant ID

        # Add current user as owner
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=current_user.id,
            role='owner'
        )
        db.session.add(membership)
        db.session.commit()

        # Create departments based on template
        created_departments = create_default_departments(tenant.id, template=template, selected_departments=selected_departments)

        # Initialize applets based on template
        if template == 'business':
            # Business template: all applets enabled
            initialize_applets_for_tenant(tenant.id, applet_keys=None, enabled=True)
        elif template == 'family':
            # Family template: only tasks applet enabled
            initialize_applets_for_tenant(tenant.id, applet_keys=['tasks', 'chat'], enabled=True)
        elif template == 'custom' and selected_applets:
            # Custom template: only selected applets enabled
            initialize_applets_for_tenant(tenant.id, applet_keys=selected_applets, enabled=True)
        else:
            # Default fallback: business template
            initialize_applets_for_tenant(tenant.id, applet_keys=None, enabled=True)

        # Create default CRM deal pipeline only if CRM applet is enabled
        from app.services.applet_manager import is_applet_enabled
        if is_applet_enabled(tenant.id, 'crm'):
            from app.services.default_crm_data import create_default_deal_pipeline
            create_default_deal_pipeline(tenant.id)

        # Trigger business intelligence scraping if website provided
        dept_count = len(created_departments)
        template_name = {
            'business': 'Business',
            'family': 'Family',
            'custom': 'Custom'
        }.get(template, 'Business')

        if website_url:
            try:
                from app.services.business_intelligence_service import scrape_business_context_async
                scrape_business_context_async(tenant.id)
                flash(f'Workspace "{name}" created with {template_name} template! Analyzing your website to personalize AI agents...', 'success')
            except Exception as e:
                print(f"Error starting business intelligence scraping: {e}")
                flash(f'Workspace "{name}" created with {dept_count} department(s) using {template_name} template!', 'success')
        else:
            flash(f'Workspace "{name}" created successfully with {dept_count} department(s) using {template_name} template!', 'success')

        # Switch to new tenant
        session['current_tenant_id'] = tenant.id

        return redirect(url_for('tenant.home'))

    return render_template('tenant/create.html', title='Create Tenant')


@tenant_bp.route('/wizard', methods=['GET', 'POST'])
@login_required
def wizard():
    """Workspace creation wizard"""
    if request.method == 'POST':
        import json
        from app.models.invitation import Invitation

        # Parse wizard data (sent as JSON from the wizard)
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Invalid request'}), 400

        # Extract data from wizard steps
        plan = data.get('plan', 'free')  # Step 1: Plan
        template = data.get('template', 'business')  # Step 2: Template

        # Step 3: Workspace Details
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        website_url = data.get('website', '').strip()
        company_size = data.get('company_size')

        # Step 4: Customization
        selected_departments = data.get('departments', [])
        selected_applets = data.get('applets', [])

        # Step 5: Invitations
        invitations = data.get('invitations', [])

        # Validation
        if not name:
            return jsonify({'error': 'Workspace name is required'}), 400

        # Check workspace limit
        if not current_user.can_create_workspace():
            return jsonify({
                'error': 'You have reached your workspace limit. Upgrade to Pro for unlimited workspaces.',
                'upgrade_required': True
            }), 403

        # Generate slug from name
        slug = name.lower().replace(' ', '-').replace('_', '-')

        # Normalize website URL
        if website_url:
            website_url = website_url.replace('http://', '').replace('https://', '')
            website_url = f'https://{website_url}'

        # Determine initial scraping status
        scraping_status = 'pending' if website_url else 'skipped'

        try:
            # Create tenant
            tenant = Tenant(
                name=name,
                slug=slug,
                description=description,
                website_url=website_url,
                company_size=company_size if company_size else None,
                context_scraping_status=scraping_status
            )
            db.session.add(tenant)
            db.session.flush()  # Get tenant ID

            # Add current user as owner
            membership = TenantMembership(
                tenant_id=tenant.id,
                user_id=current_user.id,
                role='owner'
            )
            db.session.add(membership)
            db.session.commit()

            # Create departments based on template/customization
            if template == 'custom' and selected_departments:
                created_departments = create_default_departments(
                    tenant.id,
                    template=template,
                    selected_departments=selected_departments
                )
            else:
                created_departments = create_default_departments(tenant.id, template=template)

            # Initialize applets based on template/customization
            if template == 'business':
                initialize_applets_for_tenant(tenant.id, applet_keys=None, enabled=True)
            elif template == 'personal' or template == 'family':
                # Personal/Family template: chat and tasks only
                initialize_applets_for_tenant(tenant.id, applet_keys=['tasks', 'chat'], enabled=True)
            elif template == 'custom' and selected_applets:
                initialize_applets_for_tenant(tenant.id, applet_keys=selected_applets, enabled=True)
            else:
                # Default fallback: business template
                initialize_applets_for_tenant(tenant.id, applet_keys=None, enabled=True)

            # Create default CRM deal pipeline only if CRM applet is enabled
            from app.services.applet_manager import is_applet_enabled
            if is_applet_enabled(tenant.id, 'crm'):
                from app.services.default_crm_data import create_default_deal_pipeline
                create_default_deal_pipeline(tenant.id)

            # Process invitations
            invitation_count = 0
            if invitations:
                from app.services.email_service import email_service

                for inv in invitations:
                    email = inv.get('email', '').strip().lower()
                    role = inv.get('role', 'member')

                    if not email:
                        continue

                    # Check if user already exists
                    existing_user = User.query.filter_by(email=email).first()

                    if existing_user:
                        # Add directly as member
                        existing_membership = TenantMembership.query.filter_by(
                            tenant_id=tenant.id,
                            user_id=existing_user.id
                        ).first()

                        if not existing_membership:
                            membership = TenantMembership(
                                tenant_id=tenant.id,
                                user_id=existing_user.id,
                                role=role
                            )
                            db.session.add(membership)
                            invitation_count += 1
                    else:
                        # Create invitation
                        invitation = Invitation.create_invitation(
                            email=email,
                            tenant_id=tenant.id,
                            invited_by_user_id=current_user.id,
                            role=role,
                            expires_in_days=7
                        )
                        db.session.add(invitation)
                        invitation_count += 1

                db.session.commit()

                # Send invitation emails
                for inv in invitations:
                    email = inv.get('email', '').strip().lower()

                    # Only send email for new invitations (not existing users)
                    existing_user = User.query.filter_by(email=email).first()
                    if not existing_user:
                        invitation = Invitation.query.filter_by(
                            email=email,
                            tenant_id=tenant.id,
                            status='pending'
                        ).first()

                        if invitation:
                            email_service.send_invitation_email(
                                invitation=invitation,
                                inviter_name=current_user.full_name,
                                workspace_name=tenant.name
                            )

            # Trigger business intelligence scraping if website provided
            if website_url:
                try:
                    from app.services.business_intelligence_service import scrape_business_context_async
                    scrape_business_context_async(tenant.id)
                except Exception as e:
                    print(f"Error starting business intelligence scraping: {e}")

            # Switch to new tenant
            session['current_tenant_id'] = tenant.id

            # Return success
            return jsonify({
                'success': True,
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'invitation_count': invitation_count,
                'redirect_url': url_for('tenant.home')
            })

        except Exception as e:
            db.session.rollback()
            print(f"Error creating workspace: {e}")
            return jsonify({'error': 'Failed to create workspace. Please try again.'}), 500

    # GET request - show wizard
    return render_template('tenant/wizard.html', title='Create Your Workspace')


@tenant_bp.route('/invite', methods=['GET', 'POST'])
@login_required
def invite():
    """Invite a user to the current tenant"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    form = InviteUserForm()
    if form.validate_on_submit():
        from app.models.invitation import Invitation
        from app.services.email_service import email_service

        email = form.email.data.lower()

        # Check if user exists
        user = User.query.filter_by(email=email).first()

        if user:
            # User exists - check if already a member
            existing = TenantMembership.query.filter_by(
                tenant_id=g.current_tenant.id,
                user_id=user.id
            ).first()

            if existing:
                if existing.is_active:
                    flash(f'{user.full_name} is already a member of this workspace.', 'info')
                else:
                    # Reactivate membership
                    existing.is_active = True
                    existing.role = form.role.data
                    db.session.commit()
                    flash(f'{user.full_name} has been re-added to the workspace.', 'success')
            else:
                # Create new membership
                membership = TenantMembership(
                    tenant_id=g.current_tenant.id,
                    user_id=user.id,
                    role=form.role.data
                )
                db.session.add(membership)
                db.session.commit()
                flash(f'{user.full_name} has been added to the workspace!', 'success')
        else:
            # User doesn't exist - create invitation
            # Check for existing pending invitation
            existing_invitation = Invitation.query.filter_by(
                email=email,
                tenant_id=g.current_tenant.id,
                status='pending'
            ).first()

            if existing_invitation and not existing_invitation.is_expired():
                flash(f'An invitation has already been sent to {email}.', 'info')
            else:
                # Create new invitation
                invitation = Invitation.create_invitation(
                    email=email,
                    tenant_id=g.current_tenant.id,
                    invited_by_user_id=current_user.id,
                    role=form.role.data,
                    expires_in_days=7
                )
                db.session.add(invitation)
                db.session.commit()

                # Send invitation email
                email_service.send_invitation_email(
                    invitation=invitation,
                    inviter_name=current_user.full_name,
                    workspace_name=g.current_tenant.name
                )

                flash(f'Invitation sent to {email}!', 'success')

        return redirect(url_for('tenant.home'))

    return render_template('tenant/invite.html',
                          title='Invite User',
                          form=form)


@tenant_bp.route('/invitation/<token>')
def accept_invitation(token):
    """Accept a workspace invitation"""
    from app.models.invitation import Invitation

    # Find invitation
    invitation = Invitation.query.filter_by(token=token).first()

    if not invitation:
        flash('Invalid invitation link.', 'danger')
        return redirect(url_for('auth.login'))

    # Check if expired
    if invitation.is_expired():
        invitation.mark_as_expired()
        db.session.commit()
        flash('This invitation has expired. Please contact the workspace owner for a new invitation.', 'warning')
        return redirect(url_for('auth.login'))

    # Check if already accepted
    if invitation.status == 'accepted':
        flash('This invitation has already been accepted.', 'info')
        return redirect(url_for('auth.login'))

    # Get tenant
    tenant = invitation.tenant

    if current_user.is_authenticated:
        # User is logged in
        # Check if email matches
        if current_user.email.lower() != invitation.email.lower():
            flash(f'This invitation is for {invitation.email}. Please log in with that email or create a new account.', 'warning')
            return redirect(url_for('auth.logout'))

        # Check if already a member
        existing = TenantMembership.query.filter_by(
            tenant_id=tenant.id,
            user_id=current_user.id
        ).first()

        if existing and existing.is_active:
            flash(f'You are already a member of {tenant.name}.', 'info')
            invitation.mark_as_accepted()
            db.session.commit()
            session['current_tenant_id'] = tenant.id
            return redirect(url_for('tenant.home'))

        # Add user to workspace
        if existing:
            # Reactivate membership
            existing.is_active = True
            existing.role = invitation.role
        else:
            membership = TenantMembership(
                tenant_id=tenant.id,
                user_id=current_user.id,
                role=invitation.role
            )
            db.session.add(membership)

        invitation.mark_as_accepted()
        db.session.commit()

        flash(f'Welcome to {tenant.name}!', 'success')
        session['current_tenant_id'] = tenant.id
        return redirect(url_for('tenant.home'))
    else:
        # User is not logged in - store invitation token in session and redirect to register
        session['invitation_token'] = token
        flash(f'Create an account to join {tenant.name}.', 'info')
        return redirect(url_for('auth.register'))


@tenant_bp.route('/settings')
@login_required
def settings():
    """Workspace settings and administration"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Check if user is owner or admin
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('You do not have permission to access workspace settings.', 'danger')
        return redirect(url_for('tenant.home'))

    # Get all members with their roles
    members = g.current_tenant.get_members()

    return render_template('tenant/settings.html',
                          title='Workspace Settings',
                          members=members,
                          user_role=user_role)


@tenant_bp.route('/settings/applets')
@login_required
def applets_settings():
    """Manage workspace applets"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Check if user is owner or admin
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('You do not have permission to manage applets.', 'danger')
        return redirect(url_for('tenant.home'))

    # Get applet status
    from app.services.applet_manager import get_applet_status
    applet_status = get_applet_status(g.current_tenant.id)

    return render_template('tenant/applets.html',
                          title='Manage Applets',
                          applet_status=applet_status,
                          user_role=user_role)


@tenant_bp.route('/settings/applets/<applet_key>/enable', methods=['POST'])
@login_required
def enable_applet(applet_key):
    """Enable an applet"""
    if not g.current_tenant:
        return jsonify({'error': 'No workspace selected'}), 400

    # Check if user is owner or admin
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        return jsonify({'error': 'Permission denied'}), 403

    from app.services.applet_manager import enable_applet as enable_applet_service
    success = enable_applet_service(g.current_tenant.id, applet_key)

    if success:
        return jsonify({'success': True, 'message': f'{applet_key} enabled'})
    else:
        return jsonify({'error': 'Invalid applet key'}), 400


@tenant_bp.route('/settings/applets/<applet_key>/disable', methods=['POST'])
@login_required
def disable_applet(applet_key):
    """Disable an applet"""
    if not g.current_tenant:
        return jsonify({'error': 'No workspace selected'}), 400

    # Check if user is owner or admin
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        return jsonify({'error': 'Permission denied'}), 403

    from app.services.applet_manager import disable_applet as disable_applet_service
    success = disable_applet_service(g.current_tenant.id, applet_key)

    if success:
        return jsonify({'success': True, 'message': f'{applet_key} disabled'})
    else:
        return jsonify({'error': 'Invalid applet key'}), 400


@tenant_bp.route('/agents')
@login_required
def agents():
    """Centralized AI agents management page"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get all departments with their agents
    departments = g.current_tenant.get_departments()

    # Count total agents and stats
    total_agents = 0
    active_agents = 0
    for dept in departments:
        dept_agents = dept.get_agents()
        total_agents += len(dept_agents)
        active_agents += sum(1 for agent in dept_agents if agent.is_active)

    # Check user role for edit permissions
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    can_edit = user_role in ['owner', 'admin']

    return render_template('tenant/agents.html',
                          title='AI Agents',
                          departments=departments,
                          total_agents=total_agents,
                          active_agents=active_agents,
                          can_edit=can_edit)


@tenant_bp.route('/edit-context', methods=['GET', 'POST'])
@login_required
def edit_context():
    """Edit workspace custom context"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Check if user is owner or admin
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('You do not have permission to edit workspace context.', 'danger')
        return redirect(url_for('tenant.home'))

    form = WorkspaceContextForm(obj=g.current_tenant)

    if form.validate_on_submit():
        g.current_tenant.custom_context = form.custom_context.data
        db.session.commit()

        flash('Workspace context updated successfully!', 'success')
        return redirect(url_for('tenant.settings'))

    return render_template('tenant/edit_context.html',
                          title='Edit Workspace Context',
                          form=form)


@tenant_bp.route('/delete/<int:tenant_id>', methods=['POST'])
@login_required
def delete_workspace(tenant_id):
    """Delete a workspace (owner only)"""
    from app.models.project import Project
    from app.models.task import Task

    tenant = Tenant.query.get_or_404(tenant_id)

    # Check if user is owner
    user_role = current_user.get_role_in_tenant(tenant_id)
    if user_role != 'owner':
        flash('Only workspace owners can delete a workspace.', 'danger')
        return redirect(url_for('tenant.home'))

    # Store name for flash message
    tenant_name = tenant.name

    # Manually delete projects and tasks to avoid constraint violations
    # Delete all tasks first
    Task.query.filter_by(tenant_id=tenant_id).delete()

    # Delete all projects (must iterate to trigger ORM cascades to status_columns and project_members)
    projects = Project.query.filter_by(tenant_id=tenant_id).all()
    for project in projects:
        db.session.delete(project)

    # Delete the tenant (cascades to memberships, departments, agents, messages)
    db.session.delete(tenant)
    db.session.commit()

    # Clear session
    if session.get('current_tenant_id') == tenant_id:
        session.pop('current_tenant_id', None)

    flash(f'Workspace "{tenant_name}" has been permanently deleted.', 'info')
    return redirect(url_for('tenant.home'))


@tenant_bp.route('/refresh-context', methods=['POST'])
@login_required
def refresh_context():
    """Manually trigger business context refresh"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('You do not have permission to refresh business context.', 'danger')
        return redirect(url_for('tenant.settings'))

    if not g.current_tenant.website_url:
        flash('No website URL configured.', 'warning')
        return redirect(url_for('tenant.settings'))

    # Trigger scraping
    try:
        from app.services.business_intelligence_service import scrape_business_context_async
        scrape_business_context_async(g.current_tenant.id)
        flash('Business context refresh started. This may take a moment.', 'info')
    except Exception as e:
        print(f"Error triggering business context refresh: {e}")
        flash('Failed to start business context refresh. Please try again.', 'danger')

    return redirect(url_for('tenant.settings'))


@tenant_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account_settings():
    """User account settings (personal profile, password, preferences)"""
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            # Update profile information
            current_user.first_name = request.form.get('first_name', '').strip()
            current_user.last_name = request.form.get('last_name', '').strip()
            current_user.email = request.form.get('email', '').strip().lower()

            db.session.commit()
            flash('Profile updated successfully!', 'success')

        elif action == 'change_password':
            # Change password
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            elif len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'danger')
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Password changed successfully!', 'success')

        return redirect(url_for('tenant.account_settings'))

    return render_template('tenant/account.html', title='Account Settings')


@tenant_bp.route('/upgrade')
@login_required
def upgrade():
    """Upgrade plan page"""
    return render_template('tenant/upgrade.html', title='Upgrade to Pro')
