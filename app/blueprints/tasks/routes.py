from flask import render_template, request, jsonify, g
from flask_login import login_required, current_user
from app.blueprints.tasks import tasks_bp
from app.models.task import Task
from app import db
from datetime import datetime


@tasks_bp.route('/')
@login_required
def index():
    """Tasks management page"""
    from app.models.department import Department
    from app.models.project import Project

    # Get all tasks for current tenant
    tasks = Task.query.filter_by(tenant_id=g.current_tenant.id).order_by(Task.created_at.desc()).all()

    # Get departments and projects for filtering
    departments = Department.query.filter_by(tenant_id=g.current_tenant.id).all()
    projects = Project.query.filter_by(tenant_id=g.current_tenant.id).all()

    return render_template('tasks/index.html',
                          title='Tasks',
                          tasks=tasks,
                          departments=departments,
                          projects=projects)


@tasks_bp.route('/<int:task_id>')
@login_required
def view(task_id):
    """View task details"""
    task = Task.query.get_or_404(task_id)

    # Verify tenant access
    if task.tenant_id != g.current_tenant.id:
        return "Access denied", 403

    return render_template('tasks/view.html',
                          title=task.title,
                          task=task)


@tasks_bp.route('/create', methods=['POST'])
@login_required
def create():
    """Create a new task"""
    data = request.get_json()

    title = data.get('title')
    description = data.get('description', '')
    priority = data.get('priority', 'medium')
    due_date_str = data.get('due_date')
    department_id = data.get('department_id')
    project_id = data.get('project_id')
    section = data.get('section')
    tags = data.get('tags')
    story_points = data.get('story_points')
    assigned_to_id = data.get('assigned_to_id')
    assigned_to_agent_id = data.get('assigned_to_agent_id')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    # Parse due date if provided
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    # Convert empty strings to None for integer fields
    def to_int_or_none(value):
        if value == '' or value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    # Create task
    task = Task(
        title=title,
        description=description or None,
        priority=priority,
        due_date=due_date,
        tenant_id=g.current_tenant.id,
        assigned_to_id=to_int_or_none(assigned_to_id) or current_user.id,
        assigned_to_agent_id=to_int_or_none(assigned_to_agent_id),
        created_by_id=current_user.id,
        department_id=to_int_or_none(department_id),
        project_id=to_int_or_none(project_id),
        section=section or None,
        tags=tags or None,
        story_points=to_int_or_none(story_points)
    )

    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
@login_required
def toggle_complete(task_id):
    """Toggle task completion status"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    status = task.toggle_complete()

    return jsonify({
        'id': task.id,
        'status': status,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None
    })


@tasks_bp.route('/<int:task_id>/priority', methods=['POST'])
@login_required
def update_priority(task_id):
    """Update task priority"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    new_priority = data.get('priority')

    if not new_priority:
        return jsonify({'error': 'Priority is required'}), 400

    success = task.change_priority(new_priority)

    if success:
        return jsonify({
            'id': task.id,
            'priority': task.priority
        })
    else:
        return jsonify({'error': 'Invalid priority value'}), 400


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@login_required
def delete(task_id):
    """Delete a task"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Only creator or assigned user can delete
    if task.created_by_id != current_user.id and task.assigned_to_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403

    db.session.delete(task)
    db.session.commit()

    return jsonify({'success': True})


@tasks_bp.route('/<int:task_id>/update', methods=['POST'])
@login_required
def update(task_id):
    """Update task details"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    # Update basic fields
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'priority' in data:
        task.change_priority(data['priority'])
    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
        else:
            task.due_date = None

    # Update kanban fields
    if 'project_id' in data:
        task.project_id = data['project_id']
    if 'section' in data:
        task.section = data['section']
    if 'story_points' in data:
        task.story_points = data['story_points']
    if 'assigned_to_id' in data:
        task.assigned_to_id = data['assigned_to_id']

    # Handle tags
    if 'tags' in data:
        # Expect tags as list
        if isinstance(data['tags'], list):
            task.tags = ', '.join(data['tags']) if data['tags'] else None
        else:
            task.tags = data['tags']

    db.session.commit()

    return jsonify(task.to_dict())


@tasks_bp.route('/<int:task_id>/move', methods=['POST'])
@login_required
def move_to_column(task_id):
    """Move task to a different status column"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    column_id = data.get('column_id')
    position = data.get('position')

    if not column_id:
        return jsonify({'error': 'Column ID is required'}), 400

    success = task.move_to_column(column_id, position)

    if success:
        return jsonify(task.to_dict())
    else:
        return jsonify({'error': 'Failed to move task'}), 400


@tasks_bp.route('/<int:task_id>/reorder', methods=['POST'])
@login_required
def reorder(task_id):
    """Reorder task within its current column"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    new_position = data.get('position')

    if new_position is None:
        return jsonify({'error': 'Position is required'}), 400

    success = task.reorder_in_column(new_position)

    if success:
        return jsonify(task.to_dict())
    else:
        return jsonify({'error': 'Failed to reorder task'}), 400


@tasks_bp.route('/<int:task_id>/tags', methods=['POST'])
@login_required
def manage_tags(task_id):
    """Add or remove tags from a task"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    action = data.get('action')  # 'add' or 'remove'
    tag = data.get('tag')

    if not action or not tag:
        return jsonify({'error': 'Action and tag are required'}), 400

    if action == 'add':
        task.add_tag(tag)
    elif action == 'remove':
        task.remove_tag(tag)
    else:
        return jsonify({'error': 'Invalid action'}), 400

    return jsonify(task.to_dict())
