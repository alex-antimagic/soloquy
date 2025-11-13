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
            is_primary=True
        )
        db.session.add(agent)
        db.session.commit()

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

        db.session.commit()

        flash(f'Agent "{agent.name}" updated successfully!', 'success')
        return redirect(url_for('department.view', department_id=department.id))

    return render_template('department/agent_edit.html',
                          title=f'Edit {agent.name}',
                          form=form,
                          agent=agent,
                          department=department)
