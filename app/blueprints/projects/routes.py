from flask import render_template, request, jsonify, g, redirect, url_for
from flask_login import login_required, current_user
from app.blueprints.projects import projects_bp
from app.models.project import Project, ProjectMember
from app.models.status_column import StatusColumn
from app.models.task import Task
from app import db
from datetime import datetime


@projects_bp.route('/')
@login_required
def index():
    """Projects dashboard - list all projects"""
    # Get all active projects for current tenant
    active_projects = Project.query.filter_by(
        tenant_id=g.current_tenant.id,
        is_archived=False
    ).order_by(Project.updated_at.desc()).all()

    # Get archived projects
    archived_projects = Project.query.filter_by(
        tenant_id=g.current_tenant.id,
        is_archived=True
    ).order_by(Project.updated_at.desc()).all()

    # Get task statistics
    total_tasks = Task.query.filter_by(tenant_id=g.current_tenant.id).count()
    completed_tasks = Task.query.filter_by(
        tenant_id=g.current_tenant.id,
        status='completed'
    ).count()
    pending_tasks = Task.query.filter_by(
        tenant_id=g.current_tenant.id,
        status='pending'
    ).count()
    in_progress_tasks = Task.query.filter_by(
        tenant_id=g.current_tenant.id,
        status='in_progress'
    ).count()

    # Get recently created tasks (last 10)
    recent_tasks = Task.query.filter_by(
        tenant_id=g.current_tenant.id
    ).order_by(Task.created_at.desc()).limit(10).all()

    # Get all tasks for calendar view
    all_tasks = Task.query.filter_by(
        tenant_id=g.current_tenant.id
    ).order_by(Task.created_at.desc()).all()

    return render_template('projects/index.html',
                          title='Tasks / Projects',
                          active_projects=active_projects,
                          archived_projects=archived_projects,
                          total_tasks=total_tasks,
                          completed_tasks=completed_tasks,
                          pending_tasks=pending_tasks,
                          in_progress_tasks=in_progress_tasks,
                          recent_tasks=recent_tasks,
                          all_tasks=all_tasks)


@projects_bp.route('/<int:project_id>')
@login_required
def view(project_id):
    """View project kanban board"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Get all status columns for this project
    columns = project.status_columns.order_by(StatusColumn.position).all()

    # Get all tasks for this project, grouped by column
    tasks_by_column = {}
    for column in columns:
        tasks_by_column[column.id] = column.get_tasks()

    # Get tasks without a column (for backward compatibility)
    unassigned_tasks = Task.query.filter_by(
        project_id=project.id,
        status_column_id=None
    ).order_by(Task.position).all()

    # Get project members
    members = project.get_members()

    return render_template('projects/kanban.html',
                          title=project.name,
                          project=project,
                          columns=columns,
                          tasks_by_column=tasks_by_column,
                          unassigned_tasks=unassigned_tasks,
                          members=members)


@projects_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new project"""
    if request.method == 'GET':
        return render_template('projects/create.html', title='Create Project')

    data = request.get_json() if request.is_json else request.form

    name = data.get('name')
    description = data.get('description', '')
    color = data.get('color', '#3B82F6')
    icon = data.get('icon', '')
    department_id = data.get('department_id')

    if not name:
        if request.is_json:
            return jsonify({'error': 'Project name is required'}), 400
        return render_template('projects/create.html',
                             title='Create Project',
                             error='Project name is required')

    # Create project
    project = Project(
        name=name,
        description=description,
        color=color,
        icon=icon,
        tenant_id=g.current_tenant.id,
        owner_id=current_user.id,
        department_id=department_id if department_id else None
    )

    db.session.add(project)
    db.session.flush()  # Get project ID

    # Add owner as first member
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role='owner'
    )
    db.session.add(member)

    # Create default status columns
    StatusColumn.create_default_columns(project.id)

    db.session.commit()

    if request.is_json:
        return jsonify(project.to_dict()), 201
    return redirect(url_for('projects.view', project_id=project.id))


@projects_bp.route('/<int:project_id>/update', methods=['POST'])
@login_required
def update(project_id):
    """Update project details"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Check if user is owner or editor
    member_role = project.get_member_role(current_user.id)
    if member_role not in ['owner', 'editor']:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()

    # Update fields
    if 'name' in data:
        project.name = data['name']
    if 'description' in data:
        project.description = data['description']
    if 'color' in data:
        project.color = data['color']
    if 'icon' in data:
        project.icon = data['icon']
    if 'department_id' in data:
        project.department_id = data['department_id']

    db.session.commit()

    return jsonify(project.to_dict())


@projects_bp.route('/<int:project_id>/archive', methods=['POST'])
@login_required
def archive(project_id):
    """Archive or unarchive a project"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Only owner can archive
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the project owner can archive projects'}), 403

    data = request.get_json()
    should_archive = data.get('archive', True)

    if should_archive:
        project.archive()
    else:
        project.unarchive()

    return jsonify({
        'id': project.id,
        'is_archived': project.is_archived
    })


@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@login_required
def delete(project_id):
    """Delete a project"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Only owner can delete
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the project owner can delete projects'}), 403

    # Delete project (cascades to columns and members)
    # Tasks will have their project_id set to NULL (if configured that way) or deleted
    db.session.delete(project)
    db.session.commit()

    return jsonify({'success': True})


@projects_bp.route('/<int:project_id>/members', methods=['GET'])
@login_required
def list_members(project_id):
    """Get all members of a project"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    members = []
    for pm in project.members.all():
        members.append({
            'id': pm.user.id,
            'name': pm.user.full_name,
            'email': pm.user.email,
            'role': pm.role,
            'joined_at': pm.created_at.isoformat()
        })

    return jsonify(members)


@projects_bp.route('/<int:project_id>/members/add', methods=['POST'])
@login_required
def add_member(project_id):
    """Add a member to the project"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Only owner can add members
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the project owner can add members'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    role = data.get('role', 'editor')

    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    if role not in ['owner', 'editor', 'viewer']:
        return jsonify({'error': 'Invalid role'}), 400

    project.add_member(user_id, role)

    return jsonify({'success': True})


@projects_bp.route('/<int:project_id>/members/<int:user_id>', methods=['DELETE'])
@login_required
def remove_member(project_id, user_id):
    """Remove a member from the project"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Only owner can remove members
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the project owner can remove members'}), 403

    # Cannot remove owner
    if user_id == project.owner_id:
        return jsonify({'error': 'Cannot remove project owner'}), 400

    project.remove_member(user_id)

    return jsonify({'success': True})


@projects_bp.route('/<int:project_id>/columns', methods=['GET'])
@login_required
def list_columns(project_id):
    """Get all status columns for a project"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    columns = []
    for col in project.status_columns.order_by(StatusColumn.position).all():
        columns.append(col.to_dict())

    return jsonify(columns)


@projects_bp.route('/<int:project_id>/columns/create', methods=['POST'])
@login_required
def create_column(project_id):
    """Create a new status column"""
    project = Project.query.get_or_404(project_id)

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Check if user is owner or editor
    member_role = project.get_member_role(current_user.id)
    if member_role not in ['owner', 'editor']:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()
    name = data.get('name')
    color = data.get('color', '#6B7280')
    is_done_column = data.get('is_done_column', False)
    wip_limit = data.get('wip_limit')

    if not name:
        return jsonify({'error': 'Column name is required'}), 400

    # Get max position
    max_position = db.session.query(db.func.max(StatusColumn.position)).filter(
        StatusColumn.project_id == project_id
    ).scalar() or -1

    column = StatusColumn(
        name=name,
        position=max_position + 1,
        color=color,
        is_done_column=is_done_column,
        wip_limit=wip_limit,
        project_id=project_id
    )

    db.session.add(column)
    db.session.commit()

    return jsonify(column.to_dict()), 201


@projects_bp.route('/<int:project_id>/columns/<int:column_id>/update', methods=['POST'])
@login_required
def update_column(project_id, column_id):
    """Update a status column"""
    project = Project.query.get_or_404(project_id)
    column = StatusColumn.query.get_or_404(column_id)

    # Verify column belongs to project
    if column.project_id != project_id:
        return jsonify({'error': 'Column not found in this project'}), 404

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Check if user is owner or editor
    member_role = project.get_member_role(current_user.id)
    if member_role not in ['owner', 'editor']:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()

    # Update fields
    if 'name' in data:
        column.name = data['name']
    if 'color' in data:
        column.color = data['color']
    if 'is_done_column' in data:
        column.is_done_column = data['is_done_column']
    if 'wip_limit' in data:
        column.wip_limit = data['wip_limit']
    if 'position' in data:
        column.reorder(data['position'])

    db.session.commit()

    return jsonify(column.to_dict())


@projects_bp.route('/<int:project_id>/columns/<int:column_id>', methods=['DELETE'])
@login_required
def delete_column(project_id, column_id):
    """Delete a status column"""
    project = Project.query.get_or_404(project_id)
    column = StatusColumn.query.get_or_404(column_id)

    # Verify column belongs to project
    if column.project_id != project_id:
        return jsonify({'error': 'Column not found in this project'}), 404

    # Verify user has access to this project's tenant
    if project.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Only owner can delete columns
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the project owner can delete columns'}), 403

    # Check if column has tasks
    if column.get_task_count() > 0:
        return jsonify({'error': 'Cannot delete column with tasks. Move tasks first.'}), 400

    # Delete column
    db.session.delete(column)
    db.session.commit()

    return jsonify({'success': True})
