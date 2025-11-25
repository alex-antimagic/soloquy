"""
Task Processor CRON Job
Periodically checks for pending tasks assigned to agents and processes them
"""
from datetime import datetime, timedelta
from app import db
from app.models.task import Task
from app.models.agent import Agent
from app.models.user import User
from app.services.long_running_task_service import get_long_running_task_service


def process_pending_agent_tasks():
    """
    Check for pending tasks assigned to agents and process them.
    This runs periodically (every 5-10 minutes) to handle:
    - Tasks created manually through UI
    - Tasks assigned to agents after creation
    - Backlog of pending work

    Returns:
        Dictionary with processing stats
    """
    print("[TASK_PROCESSOR] Starting periodic task processor...")

    try:
        # Get all pending/in_progress tasks assigned to agents that haven't been processed yet
        pending_tasks = Task.query.filter(
            Task.assigned_to_agent_id.isnot(None),  # Assigned to an agent
            Task.status.in_(['pending', 'in_progress']),  # Not completed
            Task.is_long_running.is_(None)  # Not yet processed for long-running detection
        ).limit(50).all()  # Process up to 50 tasks per run

        print(f"[TASK_PROCESSOR] Found {len(pending_tasks)} unprocessed agent tasks")

        if not pending_tasks:
            return {
                'success': True,
                'tasks_found': 0,
                'tasks_processed': 0,
                'tasks_queued': 0,
                'message': 'No pending tasks to process'
            }

        task_service = get_long_running_task_service()

        tasks_processed = 0
        tasks_queued = 0
        errors = []

        for task in pending_tasks:
            try:
                # Get agent and creator
                agent = task.assigned_to_agent
                creator = task.created_by

                if not agent:
                    print(f"[TASK_PROCESSOR] Task {task.id} has no agent, skipping")
                    continue

                if not creator:
                    print(f"[TASK_PROCESSOR] Task {task.id} has no creator, skipping")
                    continue

                print(f"[TASK_PROCESSOR] Processing task {task.id}: {task.title}")

                # Build message text from task
                message_text = f"{task.title}. {task.description or ''}"

                # Detect and handle long-running task
                result = task_service.detect_and_handle(
                    task=task,
                    agent=agent,
                    user=creator,
                    message_text=message_text
                )

                tasks_processed += 1

                if result.get('is_long_running'):
                    action = result.get('action_taken')
                    print(f"[TASK_PROCESSOR] Task {task.id} is long-running: {action}")

                    if action == 'queued':
                        tasks_queued += 1
                        print(f"[TASK_PROCESSOR] Task {task.id} queued for execution")
                    elif action == 'pending_approval':
                        print(f"[TASK_PROCESSOR] Task {task.id} requires approval")
                else:
                    print(f"[TASK_PROCESSOR] Task {task.id} is short-running, no special handling")

            except Exception as task_error:
                error_msg = f"Task {task.id}: {str(task_error)}"
                print(f"[TASK_PROCESSOR] Error processing task: {error_msg}")
                errors.append(error_msg)
                continue

        result = {
            'success': True,
            'tasks_found': len(pending_tasks),
            'tasks_processed': tasks_processed,
            'tasks_queued': tasks_queued,
            'errors': errors if errors else None,
            'message': f"Processed {tasks_processed} tasks, queued {tasks_queued} for execution"
        }

        print(f"[TASK_PROCESSOR] Completed: {result['message']}")
        return result

    except Exception as e:
        print(f"[TASK_PROCESSOR] Fatal error: {e}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to process pending tasks'
        }


def cleanup_stale_tasks():
    """
    Cleanup tasks that have been stuck in 'in_progress' for too long.
    This handles cases where:
    - Worker died during execution
    - RQ job failed silently
    - Network issues prevented completion

    Returns:
        Dictionary with cleanup stats
    """
    print("[TASK_CLEANUP] Starting stale task cleanup...")

    try:
        # Find tasks stuck in progress for more than 2 hours
        stale_threshold = datetime.utcnow() - timedelta(hours=2)

        stale_tasks = Task.query.filter(
            Task.status == 'in_progress',
            Task.is_long_running == True,
            Task.last_progress_update < stale_threshold
        ).all()

        print(f"[TASK_CLEANUP] Found {len(stale_tasks)} stale tasks")

        if not stale_tasks:
            return {
                'success': True,
                'stale_tasks_found': 0,
                'tasks_cleaned': 0,
                'message': 'No stale tasks to cleanup'
            }

        task_service = get_long_running_task_service()
        tasks_cleaned = 0

        for task in stale_tasks:
            try:
                print(f"[TASK_CLEANUP] Cleaning up stale task {task.id}")

                # Mark as failed
                task_service.fail_task(
                    task_id=task.id,
                    error="Task timed out - no progress update in over 2 hours",
                    retry=False
                )

                tasks_cleaned += 1

            except Exception as task_error:
                print(f"[TASK_CLEANUP] Error cleaning task {task.id}: {task_error}")
                continue

        result = {
            'success': True,
            'stale_tasks_found': len(stale_tasks),
            'tasks_cleaned': tasks_cleaned,
            'message': f"Cleaned up {tasks_cleaned} stale tasks"
        }

        print(f"[TASK_CLEANUP] Completed: {result['message']}")
        return result

    except Exception as e:
        print(f"[TASK_CLEANUP] Fatal error: {e}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to cleanup stale tasks'
        }


def periodic_task_maintenance():
    """
    Combined periodic maintenance job that:
    1. Processes pending agent tasks
    2. Cleans up stale tasks

    This is the main function called by the scheduler.
    """
    print("[TASK_MAINTENANCE] Starting periodic task maintenance...")

    # Process pending tasks
    process_result = process_pending_agent_tasks()

    # Cleanup stale tasks
    cleanup_result = cleanup_stale_tasks()

    return {
        'timestamp': datetime.utcnow().isoformat(),
        'processing': process_result,
        'cleanup': cleanup_result
    }
