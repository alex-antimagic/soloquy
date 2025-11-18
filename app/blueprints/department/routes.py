from flask import render_template, redirect, url_for, flash, request, g
from flask_login import login_required, current_user
from app import db
from app.blueprints.department import department_bp
from app.blueprints.department.forms import DepartmentForm, AgentForm
from app.models.department import Department
from app.models.agent import Agent


@department_bp.route('/')
@login_required
def index():
    """Department management page"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    departments = g.current_tenant.get_departments()
    return render_template('department/index.html',
                          title='Departments',
                          departments=departments)


@department_bp.route('/<int:department_id>')
@login_required
def view(department_id):
    """Department dashboard with metrics and data"""
    department = Department.query.get_or_404(department_id)

    # Check access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    # Get metrics
    total_messages = department.get_message_count()
    active_members = department.get_active_members()
    ai_interactions = department.get_ai_interaction_count(days=7)
    weekly_activity = department.get_weekly_activity()

    # Get recent messages
    recent_messages = department.get_recent_messages(limit=10)

    # Get primary agent for chat button
    agent = department.get_primary_agent()

    return render_template('department/view.html',
                          title=department.name,
                          department=department,
                          agent=agent,
                          total_messages=total_messages,
                          active_members=active_members,
                          ai_interactions=ai_interactions,
                          weekly_activity=weekly_activity,
                          recent_messages=recent_messages)


@department_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new department"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

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
def edit_agent(agent_id):
    """Edit an agent's configuration"""
    agent = Agent.query.get_or_404(agent_id)
    department = agent.department

    # Check tenant access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    # Check user role (owner/admin only)
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('Only workspace owners and admins can edit agents.', 'danger')
        return redirect(url_for('department.view', department_id=department.id))

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

    return render_template('department/agent_edit.html',
                          title=f'Edit {agent.name}',
                          form=form,
                          agent=agent,
                          department=department,
                          qb_integration=qb_integration)


@department_bp.route('/agent/<int:agent_id>/versions')
@login_required
def agent_versions(agent_id):
    """View version history for an agent"""
    agent = Agent.query.get_or_404(agent_id)
    department = agent.department

    # Check tenant access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    # Get all versions
    versions = agent.get_version_history()

    return render_template('department/agent_versions.html',
                          title=f'{agent.name} - Version History',
                          agent=agent,
                          department=department,
                          versions=versions)


@department_bp.route('/agent/<int:agent_id>/versions/<int:version_id>/rollback', methods=['POST'])
@login_required
def rollback_agent_version(agent_id, version_id):
    """Rollback agent to a previous version"""
    agent = Agent.query.get_or_404(agent_id)
    department = agent.department

    # Check tenant access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    # Check user role (owner/admin only)
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('Only workspace owners and admins can rollback agent versions.', 'danger')
        return redirect(url_for('department.agent_versions', agent_id=agent.id))

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
    agent = Agent.query.get_or_404(agent_id)
    department = agent.department

    # Check tenant access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

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
def tag_agent_version(agent_id, version_id):
    """Add or update a tag for an agent version"""
    from app.models.agent_version import AgentVersion

    agent = Agent.query.get_or_404(agent_id)
    department = agent.department

    # Check tenant access
    if department.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('department.index'))

    # Check user role (owner/admin only)
    user_role = current_user.get_role_in_tenant(g.current_tenant.id)
    if user_role not in ['owner', 'admin']:
        flash('Only workspace owners and admins can tag versions.', 'danger')
        return redirect(url_for('department.agent_versions', agent_id=agent.id))

    version = AgentVersion.query.get_or_404(version_id)

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
