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
    query = Task.query.filter_by(tenant_id=g.current_tenant.id)

    # Apply filters from query parameters
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter_by(status=status_filter)

    priority_filter = request.args.get('priority')
    if priority_filter:
        query = query.filter_by(priority=priority_filter)

    project_filter = request.args.get('project')
    if project_filter:
        query = query.filter_by(project_id=project_filter)

    tasks = query.order_by(Task.created_at.desc()).all()

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
    parent_task_id = data.get('parent_task_id')

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
        story_points=to_int_or_none(story_points),
        parent_task_id=to_int_or_none(parent_task_id)
    )

    db.session.add(task)
    db.session.commit()

    # Check if task is assigned to an agent and detect if it's long-running
    long_running_result = None
    if task.assigned_to_agent_id:
        try:
            from app.services.long_running_task_service import get_long_running_task_service

            agent = task.assigned_to_agent
            if agent:
                task_service = get_long_running_task_service()

                # Build message text from task details
                message_text = f"{task.title}. {task.description or ''}"

                # Detect and handle long-running task
                long_running_result = task_service.detect_and_handle(
                    task=task,
                    agent=agent,
                    user=current_user,
                    message_text=message_text
                )

                print(f"[TASK CREATE] Long-running detection result: {long_running_result}")

        except Exception as e:
            print(f"[TASK CREATE] Error detecting long-running task: {e}")
            import traceback
            traceback.print_exc()

    # Build response
    response_data = task.to_dict()

    # Add long-running info if applicable
    if long_running_result and long_running_result.get('is_long_running'):
        response_data['long_running'] = {
            'is_long_running': True,
            'action_taken': long_running_result.get('action_taken'),
            'message': long_running_result.get('message'),
            'requires_approval': long_running_result.get('plan', {}).get('requires_approval', False),
            'estimated_duration_minutes': long_running_result.get('plan', {}).get('estimated_duration_minutes')
        }

    return jsonify(response_data), 201


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


# Long-running task endpoints

@tasks_bp.route('/<int:task_id>/approve', methods=['POST'])
@login_required
def approve_task(task_id):
    """Approve a long-running task"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Verify task requires approval
    if not task.requires_approval:
        return jsonify({'error': 'Task does not require approval'}), 400

    if task.approval_status == 'approved':
        return jsonify({'error': 'Task already approved'}), 400

    try:
        from app.services.long_running_task_service import get_long_running_task_service

        task_service = get_long_running_task_service()
        result = task_service.approve_task(task_id, current_user.id)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': result.get('message'),
                'job_id': result.get('job_id'),
                'task': task.to_dict()
            })
        else:
            return jsonify({'error': result.get('error')}), 400

    except Exception as e:
        print(f"[TASK APPROVE] Error: {e}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/reject', methods=['POST'])
@login_required
def reject_task(task_id):
    """Reject a long-running task"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Verify task requires approval
    if not task.requires_approval:
        return jsonify({'error': 'Task does not require approval'}), 400

    data = request.get_json() or {}
    reason = data.get('reason')

    try:
        from app.services.long_running_task_service import get_long_running_task_service

        task_service = get_long_running_task_service()
        result = task_service.reject_task(task_id, current_user.id, reason)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': result.get('message'),
                'task': task.to_dict()
            })
        else:
            return jsonify({'error': result.get('error')}), 400

    except Exception as e:
        print(f"[TASK REJECT] Error: {e}")
        return jsonify({'error': str(e)}), 500


@tasks_bp.route('/<int:task_id>/progress', methods=['GET'])
@login_required
def get_task_progress(task_id):
    """Get progress of a long-running task"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    # Build progress response
    progress_data = {
        'task_id': task.id,
        'is_long_running': task.is_long_running or False,
        'status': task.status,
        'progress_percentage': task.progress_percentage or 0,
        'current_step': task.current_step,
        'estimated_completion': task.estimated_completion.isoformat() if task.estimated_completion else None,
        'last_progress_update': task.last_progress_update.isoformat() if task.last_progress_update else None,
        'requires_approval': task.requires_approval or False,
        'approval_status': task.approval_status,
        'execution_result': task.execution_result,
        'execution_error': task.execution_error,
        'retry_count': task.retry_count or 0
    }

    # Include execution plan if available
    if task.execution_plan:
        try:
            import json
            progress_data['execution_plan'] = json.loads(task.execution_plan)
        except:
            pass

    # Include RQ job status if available
    if task.rq_job_id:
        try:
            from redis import Redis
            from rq.job import Job
            from flask import current_app

            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            redis_conn = Redis.from_url(redis_url)
            job = Job.fetch(task.rq_job_id, connection=redis_conn)

            progress_data['job_status'] = {
                'id': job.id,
                'status': job.get_status(),
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'ended_at': job.ended_at.isoformat() if job.ended_at else None
            }
        except Exception as e:
            print(f"[TASK PROGRESS] Error fetching job status: {e}")

    return jsonify(progress_data)


@tasks_bp.route('/<int:task_id>/comments', methods=['GET', 'POST'])
@login_required
def task_comments(task_id):
    """Get or create task comments"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    if request.method == 'GET':
        # Return all comments for this task
        from app.models.task_comment import TaskComment

        comments = TaskComment.query.filter_by(
            task_id=task.id
        ).order_by(TaskComment.created_at.asc()).all()

        return jsonify({
            'task_id': task.id,
            'comments': [comment.to_dict() for comment in comments],
            'count': len(comments)
        })

    elif request.method == 'POST':
        # Create a new comment
        from app.models.task_comment import TaskComment

        data = request.get_json()
        comment_text = data.get('comment_text') or data.get('text')

        if not comment_text:
            return jsonify({'error': 'Comment text is required'}), 400

        comment_type = data.get('comment_type', 'note')

        comment = TaskComment.create_comment(
            task_id=task.id,
            comment_text=comment_text,
            user_id=current_user.id,
            comment_type=comment_type,
            is_system=False,
            tenant_id=task.tenant_id
        )

        return jsonify({
            'success': True,
            'comment': comment.to_dict()
        }), 201


@tasks_bp.route('/<int:task_id>/execution-plan', methods=['GET'])
@login_required
def get_execution_plan(task_id):
    """Get the execution plan for a long-running task"""
    task = Task.query.get_or_404(task_id)

    # Verify user has access to this task's tenant
    if task.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    if not task.execution_plan:
        return jsonify({'error': 'No execution plan found'}), 404

    try:
        import json
        plan = json.loads(task.execution_plan)

        return jsonify({
            'task_id': task.id,
            'plan': plan,
            'execution_model': task.execution_model,
            'estimated_completion': task.estimated_completion.isoformat() if task.estimated_completion else None
        })

    except Exception as e:
        print(f"[EXECUTION PLAN] Error: {e}")
        return jsonify({'error': 'Failed to load execution plan'}), 500
