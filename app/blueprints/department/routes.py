from flask import render_template, redirect, url_for, flash, request, g
from flask_login import login_required, current_user
from app import db
from app.blueprints.department import department_bp
from app.blueprints.department.forms import DepartmentForm, AgentForm
from app.models.department import Department
from app.models.agent import Agent


def get_agent_secure(agent_id):
    """
    Securely fetch agent with tenant validation built-in.
    Prevents cross-tenant data leakage.
    """
    agent = Agent.query.join(Department).filter(
        Agent.id == agent_id,
        Department.tenant_id == g.current_tenant.id
    ).first_or_404()
    return agent


def get_department_secure(department_id):
    """
    Securely fetch department with tenant validation built-in.
    Prevents cross-tenant data leakage.
    """
    department = Department.query.filter_by(
        id=department_id,
        tenant_id=g.current_tenant.id
    ).first_or_404()
    return department


def require_role(*roles):
    """
    Decorator to require specific roles in current tenant.
    Usage: @require_role('owner', 'admin')
    """
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.current_tenant:
                flash('Please select a workspace first.', 'warning')
                return redirect(url_for('tenant.home'))

            user_role = current_user.get_role_in_tenant(g.current_tenant.id)
            if user_role not in roles:
                flash(f'Access denied. Required role: {"/".join(roles)}', 'danger')
                return redirect(url_for('department.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


@department_bp.route('/')
@login_required
def index():
    """Department management page - show only accessible departments"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Get all departments and filter by user access
    all_departments = g.current_tenant.get_departments()
    accessible_departments = [
        dept for dept in all_departments
        if dept.can_user_access(current_user)
    ]

    return render_template('department/index.html',
                          title='Departments',
                          departments=accessible_departments)


@department_bp.route('/<int:department_id>')
@login_required
def view(department_id):
    """Department dashboard with metrics and data"""
    department = Department.query.get_or_404(department_id)

    # Check tenant access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    # Check department access
    if not department.can_user_access(current_user):
        flash('You do not have access to this department.', 'danger')
        return redirect(url_for('department.index'))

    # Get metrics
    total_messages = department.get_message_count()
    active_members = department.get_active_members()
    ai_interactions = department.get_ai_interaction_count(days=7)
    weekly_activity = department.get_weekly_activity()

    # Get primary agent for chat button
    agent = department.get_primary_agent()

    return render_template('department/view.html',
                          title=department.name,
                          department=department,
                          agent=agent,
                          total_messages=total_messages,
                          active_members=active_members,
                          ai_interactions=ai_interactions,
                          weekly_activity=weekly_activity)


@department_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_role('owner', 'admin')
def create():
    """Create a new department"""
    form = DepartmentForm()
    if form.validate_on_submit():
        department = Department(
            tenant_id=g.current_tenant.id,
            name=form.name.data,
            slug=form.slug.data.lower(),
            description=form.description.data,
            color=form.color.data,
            icon=form.icon.data
        )
        db.session.add(department)
        db.session.flush()  # Get department ID

        # Create default agent for the department
        agent = Agent(
            department_id=department.id,
            name=f"{form.name.data} Assistant",
            description=f"AI assistant for the {form.name.data} department",
            system_prompt=f"You are a helpful AI assistant for the {form.name.data} department. Provide assistance with tasks, questions, and information related to {form.name.data}.",
            is_primary=True,
            created_by_id=current_user.id
        )
        db.session.add(agent)
        db.session.commit()

        # Create initial version (version 1)
        try:
            agent.create_version(
                changed_by_user=current_user,
                change_summary="Initial version",
                change_type='initial'
            )
        except Exception as e:
            print(f"Error creating initial agent version: {e}")

        flash(f'Department "{form.name.data}" created successfully!', 'success')
        return redirect(url_for('department.index'))

    return render_template('department/create.html',
                          title='Create Department',
                          form=form)


@department_bp.route('/<int:department_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(department_id):
    """Edit a department"""
    department = Department.query.get_or_404(department_id)

    # Check access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    form = DepartmentForm(obj=department)
    if form.validate_on_submit():
        department.name = form.name.data
        department.slug = form.slug.data.lower()
        department.description = form.description.data
        department.color = form.color.data
        department.icon = form.icon.data
        db.session.commit()

        flash(f'Department "{department.name}" updated successfully!', 'success')
        return redirect(url_for('department.index'))

    return render_template('department/edit.html',
                          title=f'Edit {department.name}',
                          form=form,
                          department=department)


@department_bp.route('/<int:department_id>/delete', methods=['POST'])
@login_required
def delete(department_id):
    """Delete a department"""
    department = Department.query.get_or_404(department_id)

    # Check access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    name = department.name
    db.session.delete(department)
    db.session.commit()

    flash(f'Department "{name}" deleted successfully.', 'info')
    return redirect(url_for('department.index'))


@department_bp.route('/agent/<int:agent_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('owner', 'admin')
def edit_agent(agent_id):
    """Edit an agent's configuration"""
    agent = get_agent_secure(agent_id)  # Secure fetch with tenant validation
    department = agent.department

    form = AgentForm(obj=agent)

    # Get QuickBooks integration status for the template
    from app.models.integration import Integration
    qb_integration = Integration.query.filter_by(
        tenant_id=g.current_tenant.id,
        integration_type='quickbooks'
    ).first()

    if form.validate_on_submit():
        # Update agent fields
        agent.name = form.name.data
        agent.description = form.description.data
        agent.avatar_url = form.avatar_url.data
        agent.system_prompt = form.system_prompt.data
        agent.model = form.model.data
        agent.temperature = form.temperature.data
        agent.max_tokens = form.max_tokens.data
        agent.is_active = form.is_active.data
        agent.enable_quickbooks = form.enable_quickbooks.data
        agent.enable_gmail = form.enable_gmail.data if hasattr(form, 'enable_gmail') else agent.enable_gmail
        agent.enable_outlook = form.enable_outlook.data if hasattr(form, 'enable_outlook') else agent.enable_outlook
        agent.enable_google_drive = form.enable_google_drive.data if hasattr(form, 'enable_google_drive') else agent.enable_google_drive

        # Update access control
        agent.access_control = form.access_control.data
        agent.allowed_roles = form.allowed_roles_str.data if form.allowed_roles_str.data else None
        agent.allowed_department_ids = form.allowed_department_ids_str.data if form.allowed_department_ids_str.data else None
        agent.allowed_user_ids = form.allowed_user_ids_str.data if form.allowed_user_ids_str.data else None

        # Commit agent changes first (without versioning)
        db.session.commit()

        # Create new version (auto-generates change summary)
        try:
            new_version = agent.create_version(
                changed_by_user=current_user,
                change_type='update'
            )
            flash(f'Agent "{agent.name}" updated successfully! (Version {new_version.version_number} created)', 'success')
        except Exception as e:
            print(f"Error creating agent version: {e}")
            flash(f'Agent "{agent.name}" updated successfully!', 'success')

        return redirect(url_for('department.view', department_id=department.id))

    # Populate hidden fields on GET request
    if not form.is_submitted():
        form.allowed_roles_str.data = agent.allowed_roles
        form.allowed_department_ids_str.data = agent.allowed_department_ids
        form.allowed_user_ids_str.data = agent.allowed_user_ids

    # Get workspace members and departments for access control UI
    workspace_members = g.current_tenant.get_members()
    workspace_departments = g.current_tenant.get_departments()

    return render_template('department/agent_edit.html',
                          title=f'Edit {agent.name}',
                          form=form,
                          agent=agent,
                          department=department,
                          qb_integration=qb_integration,
                          workspace_members=workspace_members,
                          workspace_departments=workspace_departments)


@department_bp.route('/agent/<int:agent_id>/versions')
@login_required
def agent_versions(agent_id):
    """View version history for an agent"""
    agent = get_agent_secure(agent_id)  # Secure fetch with tenant validation
    department = agent.department

    # Get all versions
    versions = agent.get_version_history()

    return render_template('department/agent_versions.html',
                          title=f'{agent.name} - Version History',
                          agent=agent,
                          department=department,
                          versions=versions)


@department_bp.route('/agent/<int:agent_id>/versions/<int:version_id>/rollback', methods=['POST'])
@login_required
@require_role('owner', 'admin')
def rollback_agent_version(agent_id, version_id):
    """Rollback agent to a previous version"""
    agent = get_agent_secure(agent_id)  # Secure fetch with tenant validation

    # Get rollback reason from form
    from flask import request
    reason = request.form.get('reason', '')

    try:
        new_version = agent.rollback_to_version(
            version_id=version_id,
            current_user=current_user,
            reason=reason if reason else None
        )
        flash(f'Successfully rolled back to version {new_version.version_number}!', 'success')
    except ValueError as e:
        flash(f'Error: {str(e)}', 'danger')
    except Exception as e:
        print(f"Error rolling back agent: {e}")
        flash('An error occurred while rolling back the agent.', 'danger')

    return redirect(url_for('department.agent_versions', agent_id=agent.id))


@department_bp.route('/agent/<int:agent_id>/versions/compare')
@login_required
def compare_agent_versions(agent_id):
    """Compare two versions of an agent side-by-side"""
    agent = get_agent_secure(agent_id)  # Secure fetch with tenant validation
    department = agent.department

    # Get version IDs from query params
    from flask import request
    v1_id = request.args.get('v1', type=int)
    v2_id = request.args.get('v2', type=int)

    if not v1_id or not v2_id:
        flash('Please select two versions to compare.', 'warning')
        return redirect(url_for('department.agent_versions', agent_id=agent.id))

    try:
        comparison = agent.compare_versions(v1_id, v2_id)
    except ValueError as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('department.agent_versions', agent_id=agent.id))

    # Generate line-by-line diff for text fields
    import difflib
    for change in comparison.get('changes', []):
        if change.get('type') == 'text' and change.get('old_value') and change.get('new_value'):
            old_lines = change['old_value'].split('\n')
            new_lines = change['new_value'].split('\n')

            # Create unified diff
            diff = difflib.unified_diff(
                old_lines,
                new_lines,
                lineterm='',
                n=3  # Context lines
            )

            # Convert to HTML-friendly format
            diff_lines = []
            for line in diff:
                if line.startswith('---') or line.startswith('+++'):
                    continue
                elif line.startswith('@@'):
                    diff_lines.append({'type': 'context', 'content': line})
                elif line.startswith('-'):
                    diff_lines.append({'type': 'remove', 'content': line[1:]})
                elif line.startswith('+'):
                    diff_lines.append({'type': 'add', 'content': line[1:]})
                else:
                    diff_lines.append({'type': 'unchanged', 'content': line[1:] if line.startswith(' ') else line})

            change['diff_lines'] = diff_lines

    return render_template('department/agent_compare.html',
                          title=f'Compare Versions - {agent.name}',
                          agent=agent,
                          department=department,
                          comparison=comparison)


@department_bp.route('/agent/<int:agent_id>/versions/<int:version_id>/tag', methods=['POST'])
@login_required
@require_role('owner', 'admin')
def tag_agent_version(agent_id, version_id):
    """Add or update a tag for an agent version"""
    from app.models.agent_version import AgentVersion

    agent = get_agent_secure(agent_id)  # Secure fetch with tenant validation

    # Fetch version with tenant validation through agent relationship
    version = AgentVersion.query.join(Agent).join(Department).filter(
        AgentVersion.id == version_id,
        AgentVersion.agent_id == agent.id,
        Department.tenant_id == g.current_tenant.id
    ).first_or_404()

    if version.agent_id != agent.id:
        flash('Invalid version.', 'danger')
        return redirect(url_for('department.agent_versions', agent_id=agent.id))

    from flask import request
    tag = request.form.get('tag', '').strip()

    # Allow removing tag
    if tag == '' or tag == 'none':
        version.version_tag = None
        flash('Tag removed.', 'success')
    else:
        version.version_tag = tag
        flash(f'Version {version.version_number} tagged as "{tag}".', 'success')

    db.session.commit()

    return redirect(url_for('department.agent_versions', agent_id=agent.id))


@department_bp.route('/agent/<int:agent_id>/export')
@login_required
def export_agent(agent_id):
    """Export agent configuration as JSON file"""
    agent = get_agent_secure(agent_id)  # Secure fetch with tenant validation

    # Export to JSON
    import json
    import re
    from flask import make_response
    from werkzeug.utils import secure_filename

    agent_json = agent.export_to_json()

    # Create filename - sanitize to prevent path traversal
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', agent.name.lower())
    safe_name = safe_name[:50]  # Limit length
    filename = f"{safe_name}_config.json"
    filename = secure_filename(filename)  # Additional sanitization

    # Create response
    response = make_response(json.dumps(agent_json, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    return response


@department_bp.route('/<int:department_id>/agent/import', methods=['GET', 'POST'])
@login_required
@require_role('owner', 'admin')
def import_agent(department_id):
    """Import agent from JSON file"""
    department = get_department_secure(department_id)  # Secure fetch with tenant validation

    if request.method == 'POST':
        # Check if file was uploaded
        if 'agent_file' not in request.files:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('department.import_agent', department_id=department.id))

        file = request.files['agent_file']

        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('department.import_agent', department_id=department.id))

        # Validate file extension
        if not file.filename.endswith('.json'):
            flash('Invalid file type. Please upload a .json file.', 'danger')
            return redirect(url_for('department.import_agent', department_id=department.id))

        try:
            # Parse JSON
            import json
            agent_data = json.load(file)

            # Import agent
            new_agent, version_number, was_created = Agent.import_from_json(
                json_data=agent_data,
                department_id=department.id,
                created_by_user=current_user
            )

            flash(f'Agent "{new_agent.name}" imported successfully!', 'success')
            return redirect(url_for('department.edit_agent', agent_id=new_agent.id))

        except json.JSONDecodeError:
            flash('Invalid JSON file. Please check the file format.', 'danger')
            return redirect(url_for('department.import_agent', department_id=department.id))
        except ValueError as e:
            # ValueError contains user-friendly validation messages
            flash(f'Import failed: {str(e)}', 'danger')
            return redirect(url_for('department.import_agent', department_id=department.id))
        except Exception as e:
            # Log detailed error internally, show generic message to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Agent import failed for user {current_user.id}: {type(e).__name__}: {str(e)}")
            flash('Unable to import agent configuration. Please check the file and try again.', 'danger')
            return redirect(url_for('department.import_agent', department_id=department.id))

    return render_template('department/agent_import.html',
                          title='Import Agent',
                          department=department)


@department_bp.route('/<int:department_id>/members')
@login_required
@require_role('owner', 'admin')
def manage_members(department_id):
    """View and manage department members (admin only)"""
    department = get_department_secure(department_id)

    # Get current members
    members = department.get_members()

    # Get available users (workspace members not in department or inactive)
    from app.models.department_membership import DepartmentMembership
    all_workspace_members = g.current_tenant.get_members()

    # Get current active member IDs
    active_member_ids = [m.id for m in members]

    # Filter available users (not admins, not already members)
    available_users = []
    for user in all_workspace_members:
        user_role = user.get_role_in_tenant(g.current_tenant.id)
        # Skip admins (they always have access)
        if user_role in ['owner', 'admin']:
            continue
        # Skip if already a member
        if user.id in active_member_ids:
            continue
        available_users.append(user)

    return render_template('department/members.html',
                          title=f'{department.name} - Members',
                          department=department,
                          members=members,
                          available_users=available_users)


@department_bp.route('/<int:department_id>/members/add', methods=['POST'])
@login_required
@require_role('owner', 'admin')
def add_member(department_id):
    """Add a user to department (admin only)"""
    department = get_department_secure(department_id)

    user_id = request.form.get('user_id', type=int)

    if not user_id:
        flash('Please select a user.', 'danger')
        return redirect(url_for('department.manage_members', department_id=department.id))

    from app.models.user import User
    from app.models.tenant import TenantMembership

    # Fetch user with tenant scope validation (secure by default)
    user = User.query.join(TenantMembership).filter(
        User.id == user_id,
        TenantMembership.tenant_id == g.current_tenant.id,
        TenantMembership.is_active == True
    ).first()

    if not user:
        flash('User not found in workspace.', 'danger')
        return redirect(url_for('department.manage_members', department_id=department.id))

    # Add member
    department.add_member(user)
    db.session.commit()

    flash(f'{user.full_name} added to {department.name}', 'success')
    return redirect(url_for('department.manage_members', department_id=department.id))


@department_bp.route('/<int:department_id>/members/remove', methods=['POST'])
@login_required
@require_role('owner', 'admin')
def remove_member(department_id):
    """Remove a user from department (admin only)"""
    department = get_department_secure(department_id)

    user_id = request.form.get('user_id', type=int)

    if not user_id:
        flash('Invalid request.', 'danger')
        return redirect(url_for('department.manage_members', department_id=department.id))

    from app.models.user import User
    from app.models.tenant import TenantMembership

    # Fetch user with tenant scope validation (secure by default)
    user = User.query.join(TenantMembership).filter(
        User.id == user_id,
        TenantMembership.tenant_id == g.current_tenant.id,
        TenantMembership.is_active == True
    ).first()

    if not user:
        flash('User not found in workspace.', 'danger')
        return redirect(url_for('department.manage_members', department_id=department.id))

    # Verify user is not an admin (admins always have access, can't be removed)
    user_role = user.get_role_in_tenant(g.current_tenant.id)
    if user_role in ['owner', 'admin']:
        flash('Cannot remove workspace admins from departments (they always have access).', 'warning')
        return redirect(url_for('department.manage_members', department_id=department.id))

    # Remove member
    department.remove_member(user)
    db.session.commit()

    flash(f'{user.full_name} removed from {department.name}', 'info')
    return redirect(url_for('department.manage_members', department_id=department.id))


@department_bp.route('/<int:department_id>/access', methods=['POST'])
@login_required
@require_role('owner', 'admin')
def update_access_control(department_id):
    """Update department access control mode (admin only)"""
    department = get_department_secure(department_id)

    access_control = request.form.get('access_control')

    if access_control not in ['all', 'members']:
        flash('Invalid access control mode.', 'danger')
        return redirect(url_for('department.edit', department_id=department.id))

    department.access_control = access_control
    db.session.commit()

    if access_control == 'all':
        flash(f'{department.name} is now accessible to all workspace members.', 'success')
    else:
        flash(f'{department.name} is now restricted to department members only.', 'info')

    return redirect(url_for('department.edit', department_id=department.id))
