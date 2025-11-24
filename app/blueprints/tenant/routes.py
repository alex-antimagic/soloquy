from flask import render_template, redirect, url_for, flash, request, session, g, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.blueprints.tenant import tenant_bp
from app.blueprints.tenant.forms import InviteUserForm, WorkspaceContextForm
from app.models.tenant import Tenant, TenantMembership
from app.models.department import Department
from app.models.user import User
from app.services.default_departments import create_default_departments
from app.services.applet_manager import initialize_applets_for_tenant
from app.services.cloudinary_service import upload_image
from app.utils.security_decorators import require_tenant_role


@tenant_bp.route('/')
@login_required
def home():
    """Main dashboard - shows current tenant overview"""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models.agent import Agent
    from app.models.message import Message
    from app.models.task import Task
    from app.services.applet_manager import is_applet_enabled

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
    total_agents = 0
    message_count = 0
    task_stats = {}
    deal_pipeline = []
    recent_activity = []

    if g.current_tenant:
        departments = g.current_tenant.get_departments()

        # Calculate total active agents across all departments
        total_agents = db.session.query(Agent).join(Department).filter(
            Department.tenant_id == g.current_tenant.id,
            Agent.is_active == True
        ).count()

        # Calculate active tasks count (pending + in_progress)
        active_tasks_count = db.session.query(Task).filter(
            Task.tenant_id == g.current_tenant.id,
            Task.status.in_(['pending', 'in_progress'])
        ).count()

        # Get task statistics (if tasks applet enabled)
        if is_applet_enabled(g.current_tenant.id, 'tasks') or is_applet_enabled(g.current_tenant.id, 'projects'):
            task_data = db.session.query(
                Task.status, func.count(Task.id)
            ).filter(
                Task.tenant_id == g.current_tenant.id
            ).group_by(Task.status).all()

            task_stats = {
                'pending': 0,
                'in_progress': 0,
                'completed': 0
            }
            for status, count in task_data:
                if status in task_stats:
                    task_stats[status] = count

        # Get deal pipeline (if CRM applet enabled)
        if is_applet_enabled(g.current_tenant.id, 'crm'):
            from app.models.deal import Deal
            from app.models.deal_stage import DealStage

            pipeline_data = db.session.query(
                DealStage.name, func.sum(Deal.amount)
            ).join(Deal, Deal.stage_id == DealStage.id).filter(
                Deal.tenant_id == g.current_tenant.id,
                Deal.status == 'open'
            ).group_by(DealStage.name, DealStage.position).order_by(DealStage.position).all()

            deal_pipeline = [{'stage': name, 'amount': float(amount or 0)} for name, amount in pipeline_data]

        # Get recent activity (last 10 items) - team collaboration only
        try:
            # Get recent tasks (if enabled)
            if is_applet_enabled(g.current_tenant.id, 'tasks') or is_applet_enabled(g.current_tenant.id, 'projects'):
                recent_tasks = db.session.query(Task).filter(
                    Task.tenant_id == g.current_tenant.id
                ).order_by(Task.created_at.desc()).limit(5).all()

                for task in recent_tasks:
                    assignee_name = 'Unassigned'
                    if task.assigned_to:
                        assignee_name = task.assigned_to.full_name
                    elif task.assigned_to_agent:
                        assignee_name = task.assigned_to_agent.name

                    recent_activity.append({
                        'type': 'task',
                        'icon': 'check2-square',
                        'text': f'{assignee_name}: {task.title}',
                        'time': task.created_at,
                        'url': url_for('tasks.index')
                    })

            # Get recent deals (if CRM enabled)
            if is_applet_enabled(g.current_tenant.id, 'crm'):
                from app.models.deal import Deal
                recent_deals = db.session.query(Deal).filter(
                    Deal.tenant_id == g.current_tenant.id
                ).order_by(Deal.created_at.desc()).limit(5).all()

                for deal in recent_deals:
                    recent_activity.append({
                        'type': 'deal',
                        'icon': 'currency-dollar',
                        'text': f'Deal created: {deal.title} (${deal.amount:,.0f})',
                        'time': deal.created_at,
                        'url': url_for('crm.deal_detail', deal_id=deal.id)
                    })

            # Sort by time and limit to 10
            recent_activity = sorted(recent_activity, key=lambda x: x['time'], reverse=True)[:10]
        except Exception as e:
            print(f"Error fetching recent activity: {e}")
            recent_activity = []

    return render_template('tenant/dashboard.html',
                           title='Dashboard',
                           tenants=tenants,
                           departments=departments,
                           total_agents=total_agents,
                           active_tasks_count=active_tasks_count,
                           task_stats=task_stats,
                           deal_pipeline=deal_pipeline,
                           recent_activity=recent_activity)


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
    # Pass user's plan to skip plan selection step
    user_plan = current_user.plan or 'free'
    return render_template('tenant/wizard.html', title='Create Your Workspace', user_plan=user_plan)


@tenant_bp.route('/invite', methods=['GET', 'POST'])
@login_required
@require_tenant_role('owner', 'admin')
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
@require_tenant_role('owner', 'admin')
def settings():
    """Workspace settings and administration"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get all members with their roles
    members = g.current_tenant.get_members()
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)

    return render_template('tenant/settings.html',
                          title='Workspace Settings',
                          members=members,
                          user_role=user_role)


@tenant_bp.route('/settings/applets')
@login_required
@require_tenant_role('owner', 'admin')
def applets_settings():
    """Manage workspace applets"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get applet status
    from app.services.applet_manager import get_applet_status
    applet_status = get_applet_status(g.current_tenant.id)
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)

    return render_template('tenant/applets.html',
                          title='Manage Applets',
                          applet_status=applet_status,
                          user_role=user_role)


@tenant_bp.route('/settings/applets/<applet_key>/enable', methods=['POST'])
@login_required
@require_tenant_role('owner', 'admin')
def enable_applet(applet_key):
    """Enable an applet"""
    if not g.current_tenant:
        return jsonify({'error': 'No workspace selected'}), 400

    from app.services.applet_manager import enable_applet as enable_applet_service
    success = enable_applet_service(g.current_tenant.id, applet_key)

    if success:
        return jsonify({'success': True, 'message': f'{applet_key} enabled'})
    else:
        return jsonify({'error': 'Invalid applet key'}), 400


@tenant_bp.route('/settings/applets/<applet_key>/disable', methods=['POST'])
@login_required
@require_tenant_role('owner', 'admin')
def disable_applet(applet_key):
    """Disable an applet"""
    if not g.current_tenant:
        return jsonify({'error': 'No workspace selected'}), 400

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

    # Count total agents and stats, filtering by access
    total_agents = 0
    active_agents = 0
    for dept in departments:
        dept_agents = dept.get_agents()
        # Filter agents by user access
        dept.accessible_agents = [agent for agent in dept_agents if agent.can_user_access(current_user)]
        total_agents += len(dept.accessible_agents)
        active_agents += sum(1 for agent in dept.accessible_agents if agent.is_active)

    # Check user role for edit permissions
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    can_edit = user_role in ['owner', 'admin']

    return render_template('tenant/agents.html',
                          title='AI Agents',
                          departments=departments,
                          total_agents=total_agents,
                          active_agents=active_agents,
                          can_edit=can_edit)


@tenant_bp.route('/agents/create', methods=['GET', 'POST'])
@login_required
def create_agent():
    """Create a personal AI agent"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    if request.method == 'POST':
        # Get or create Personal department
        from app.models.department import Department
        from app.models.agent import Agent

        personal_dept = Department.query.filter_by(
            tenant_id=g.current_tenant.id,
            slug='personal'
        ).first()

        if not personal_dept:
            personal_dept = Department(
                tenant_id=g.current_tenant.id,
                name='Personal',
                slug='personal',
                description='Personal AI assistants',
                color='#8b5cf6',
                icon='👤'
            )
            db.session.add(personal_dept)
            db.session.flush()

            # Create department channel for personal agents
            from app.models.channel import Channel
            personal_channel = Channel(
                name='Personal',
                slug='personal',
                department_id=personal_dept.id,
                tenant_id=g.current_tenant.id,
                is_department_channel=True,
                is_private=False
            )
            db.session.add(personal_channel)

        # Create the agent
        # Personal agents are private by default (only accessible by creator)
        import json
        agent = Agent(
            department_id=personal_dept.id,
            created_by_id=current_user.id,
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip(),
            system_prompt=request.form.get('system_prompt', '').strip(),
            is_active=True,
            is_primary=False,
            model=request.form.get('model', 'claude-3-5-sonnet-20241022'),
            temperature=float(request.form.get('temperature', 1.0)),
            max_tokens=int(request.form.get('max_tokens', 4096)),
            enable_gmail=request.form.get('enable_gmail') == 'on',
            enable_outlook=request.form.get('enable_outlook') == 'on',
            enable_google_drive=request.form.get('enable_google_drive') == 'on',
            # Private by default - only creator can access
            access_control='users',
            allowed_user_ids=json.dumps([current_user.id])
        )
        db.session.add(agent)
        db.session.commit()

        flash(f'Agent "{agent.name}" created successfully!', 'success')
        return redirect(url_for('chat.agent_chat', agent_id=agent.id))

    return render_template('tenant/create_agent.html',
                          title='Create AI Agent')


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


@tenant_bp.route('/delete/<int:tenant_id>', methods=['GET', 'POST'])
@login_required
@require_tenant_role('owner')
def delete_workspace(tenant_id):
    """Delete a workspace (owner only)"""
    from app.models.project import Project
    from app.models.task import Task

    tenant = Tenant.query.get_or_404(tenant_id)

    # Verify user is accessing their own tenant
    if tenant.id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('tenant.home'))

    # GET request - show confirmation page
    if request.method == 'GET':
        return render_template('tenant/delete_confirm.html',
                             title='Delete Workspace',
                             tenant=tenant)

    # POST request - perform deletion
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
@require_tenant_role('owner', 'admin')
def refresh_context():
    """Manually trigger business context refresh"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

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


@tenant_bp.route('/add-website', methods=['POST'])
@login_required
def add_website():
    """Add website URL to existing workspace (post-onboarding)"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('You do not have permission to add a website.', 'danger')
        return redirect(url_for('tenant.settings'))

    # Get form data
    website_url = request.form.get('website_url', '').strip()
    company_size = request.form.get('company_size', '').strip()

    if not website_url:
        flash('Website URL is required.', 'danger')
        return redirect(url_for('tenant.settings'))

    # Normalize website URL - add https:// if missing
    website_url = website_url.replace('http://', '').replace('https://', '')
    website_url = f'https://{website_url}'

    # Update tenant
    g.current_tenant.website_url = website_url
    g.current_tenant.company_size = company_size if company_size else None
    g.current_tenant.context_scraping_status = 'pending'
    db.session.commit()

    # Trigger business intelligence scraping
    try:
        from app.services.business_intelligence_service import scrape_business_context_async
        scrape_business_context_async(g.current_tenant.id)
        flash('Website added! Analyzing your website to personalize AI agents...', 'success')
    except Exception as e:
        print(f"Error starting business intelligence scraping: {e}")
        flash('Website added, but failed to start analysis. Please try refreshing the context.', 'warning')

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
            current_user.title = request.form.get('title', '').strip() or None  # Store None if empty

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

        elif action == 'remove_avatar':
            # Remove avatar
            current_user.avatar_url = None
            db.session.commit()
            flash('Profile picture removed successfully!', 'success')

        elif action == 'update_theme':
            # Update theme preference
            theme = request.form.get('theme_preference', 'dark')
            if theme in ['dark', 'light']:
                current_user.theme_preference = theme
                db.session.commit()
                flash(f'Theme changed to {theme} mode!', 'success')
            else:
                flash('Invalid theme preference.', 'danger')

        return redirect(url_for('tenant.account_settings'))

    return render_template('tenant/account.html', title='Account Settings')


@tenant_bp.route('/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload user avatar image"""
    try:
        # Validate file upload
        if 'avatar' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        file = request.files['avatar']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        max_size = current_app.config.get('MAX_FILE_SIZE', 10 * 1024 * 1024)
        if file_size > max_size:
            return jsonify({'error': f'File too large. Maximum size is {max_size // (1024 * 1024)}MB'}), 400

        # Validate file type
        allowed_extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

        # Upload to Cloudinary
        file.seek(0)
        upload_result = upload_image(file, folder="avatars")

        # Update user's avatar_url
        current_user.avatar_url = upload_result['secure_url']
        db.session.commit()

        return jsonify({
            'success': True,
            'avatar_url': upload_result['secure_url']
        })

    except Exception as e:
        current_app.logger.error(f"Error uploading avatar: {str(e)}")
        return jsonify({'error': 'Failed to upload avatar. Please try again.'}), 500


@tenant_bp.route('/upgrade')
@login_required
def upgrade():
    """Upgrade plan page"""
    return render_template('tenant/upgrade.html', title='Upgrade to Pro')
