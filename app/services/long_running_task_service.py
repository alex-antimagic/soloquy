"""
Long Running Task Service
Orchestrates detection, planning, queueing, and execution of long-running agent tasks
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import current_app
from app import db
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.services.ai_service import get_ai_service
from redis import Redis
from rq import Queue
from rq.job import Job


class LongRunningTaskService:
    """Service for handling long-running agent tasks"""

    def __init__(self):
        self.ai_service = get_ai_service()

        # Initialize Redis and RQ
        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')

        # Configure SSL for Heroku Redis
        if redis_url.startswith('rediss://'):
            self.redis_conn = Redis.from_url(redis_url, ssl_cert_reqs=None)
        else:
            self.redis_conn = Redis.from_url(redis_url)

        # Define queues with different priorities
        self.high_queue = Queue('high', connection=self.redis_conn)
        self.default_queue = Queue('default', connection=self.redis_conn)
        self.low_queue = Queue('low', connection=self.redis_conn)

    def detect_and_handle(
        self,
        task: Task,
        agent,
        user,
        message_text: str
    ) -> Dict[str, Any]:
        """
        Detect if a task is long-running and handle accordingly.

        Args:
            task: Task model instance
            agent: Agent that will execute the task
            user: User who created the task
            message_text: Original message text from chat

        Returns:
            Dictionary with:
                - is_long_running: bool
                - action_taken: str ('queued', 'pending_approval', 'execute_now')
                - plan: Dict (if long-running)
                - message: str (message to show user)
        """
        try:
            # Step 1: Detect if task is long-running using Haiku
            print(f"[LONG_TASK] Detecting if task {task.id} is long-running...")

            task_context = {
                'assigned_to': agent.name,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'project': task.project.name if task.project else None
            }

            detection_result = self.ai_service.detect_long_running_task(
                task_description=task.description or task.title,
                task_context=task_context
            )

            print(f"[LONG_TASK] Detection result: {detection_result}")

            # If not long-running, execute normally
            if not detection_result['is_long_running']:
                return {
                    'is_long_running': False,
                    'action_taken': 'execute_now',
                    'message': f"Task will be completed quickly (estimated {detection_result['estimated_duration_seconds']}s)"
                }

            # Step 2: Generate execution plan using Sonnet
            print(f"[LONG_TASK] Task is long-running. Generating execution plan...")

            tenant_context = {
                'tenant_name': agent.department.tenant.name,
                'industry': getattr(agent.department.tenant, 'industry', 'General'),
                'user_name': user.full_name
            }

            plan = self.ai_service.generate_execution_plan(
                task_description=task.description or task.title,
                task_id=task.id,
                agent_name=agent.name,
                tenant_context=tenant_context
            )

            print(f"[LONG_TASK] Execution plan generated: {plan}")

            # Step 3: Update task with long-running metadata
            task.is_long_running = True
            task.execution_plan = json.dumps(plan)
            task.execution_model = 'claude-sonnet-4-5-20250929'
            task.requires_approval = plan['requires_approval']
            task.estimated_completion = datetime.utcnow() + timedelta(minutes=plan['estimated_duration_minutes'])

            if plan['requires_approval']:
                task.approval_status = 'pending'

            db.session.commit()

            # Step 4: Create system comment with plan
            self._create_plan_comment(task, plan, agent)

            # Step 5: Handle based on approval requirement
            if plan['requires_approval']:
                # Wait for user approval
                return {
                    'is_long_running': True,
                    'action_taken': 'pending_approval',
                    'plan': plan,
                    'message': f"I've created a detailed plan for this task (estimated {plan['estimated_duration_minutes']} minutes). " +
                              f"This task requires your approval because: {plan['approval_reasoning']}. " +
                              "Please review the plan and approve to proceed."
                }
            else:
                # Queue for immediate execution
                job = self._queue_task(task, agent, user, plan)

                return {
                    'is_long_running': True,
                    'action_taken': 'queued',
                    'plan': plan,
                    'job_id': job.id if job else None,
                    'message': f"Task queued for execution (estimated {plan['estimated_duration_minutes']} minutes). " +
                              "I'll notify you when it's complete."
                }

        except Exception as e:
            print(f"[LONG_TASK] Error in detect_and_handle: {e}")
            import traceback
            traceback.print_exc()

            # Fallback to normal execution
            return {
                'is_long_running': False,
                'action_taken': 'execute_now',
                'error': str(e),
                'message': "Error detecting task complexity, will execute normally"
            }

    def approve_task(self, task_id: int, user_id: int) -> Dict[str, Any]:
        """
        Approve a task and queue it for execution.

        Args:
            task_id: ID of task to approve
            user_id: ID of user approving

        Returns:
            Result dictionary with job_id and status
        """
        task = Task.query.get(task_id)
        if not task:
            return {'success': False, 'error': 'Task not found'}

        if not task.requires_approval:
            return {'success': False, 'error': 'Task does not require approval'}

        if task.approval_status == 'approved':
            return {'success': False, 'error': 'Task already approved'}

        try:
            # Update approval status
            task.approval_status = 'approved'
            task.approved_by_id = user_id
            task.approved_at = datetime.utcnow()
            db.session.commit()

            # Create approval comment
            TaskComment.create_comment(
                task_id=task.id,
                comment_text=f"Task approved and queued for execution",
                user_id=user_id,
                comment_type='approval',
                is_system=True,
                tenant_id=task.tenant_id
            )

            # Load execution plan
            plan = json.loads(task.execution_plan) if task.execution_plan else {}

            # Get agent
            agent = task.assigned_to_agent
            if not agent:
                return {'success': False, 'error': 'No agent assigned to task'}

            # Queue the task
            job = self._queue_task(task, agent, task.created_by, plan)

            return {
                'success': True,
                'job_id': job.id if job else None,
                'message': 'Task approved and queued for execution'
            }

        except Exception as e:
            print(f"[LONG_TASK] Error approving task: {e}")
            return {'success': False, 'error': str(e)}

    def reject_task(self, task_id: int, user_id: int, reason: str = None) -> Dict[str, Any]:
        """
        Reject a task that requires approval.

        Args:
            task_id: ID of task to reject
            user_id: ID of user rejecting
            reason: Optional rejection reason

        Returns:
            Result dictionary
        """
        task = Task.query.get(task_id)
        if not task:
            return {'success': False, 'error': 'Task not found'}

        if not task.requires_approval:
            return {'success': False, 'error': 'Task does not require approval'}

        try:
            # Update approval status
            task.approval_status = 'rejected'
            task.status = 'completed'  # Mark as completed (rejected)
            db.session.commit()

            # Create rejection comment
            comment_text = f"Task rejected"
            if reason:
                comment_text += f": {reason}"

            TaskComment.create_comment(
                task_id=task.id,
                comment_text=comment_text,
                user_id=user_id,
                comment_type='approval',
                is_system=True,
                tenant_id=task.tenant_id
            )

            return {
                'success': True,
                'message': 'Task rejected'
            }

        except Exception as e:
            print(f"[LONG_TASK] Error rejecting task: {e}")
            return {'success': False, 'error': str(e)}

    def update_progress(
        self,
        task_id: int,
        progress_percentage: int,
        current_step: str,
        agent_id: int = None
    ) -> Dict[str, Any]:
        """
        Update task progress during execution.

        Args:
            task_id: ID of task being executed
            progress_percentage: Completion percentage (0-100)
            current_step: Description of current step
            agent_id: Optional agent ID for comment

        Returns:
            Result dictionary
        """
        task = Task.query.get(task_id)
        if not task:
            return {'success': False, 'error': 'Task not found'}

        try:
            # Update progress
            task.progress_percentage = progress_percentage
            task.current_step = current_step
            task.last_progress_update = datetime.utcnow()
            task.status = 'in_progress'
            db.session.commit()

            # Create progress comment
            TaskComment.create_comment(
                task_id=task.id,
                comment_text=f"Progress: {progress_percentage}% - {current_step}",
                agent_id=agent_id,
                comment_type='progress_update',
                is_system=True,
                meta_data=json.dumps({
                    'progress_percentage': progress_percentage,
                    'current_step': current_step
                }),
                tenant_id=task.tenant_id
            )

            # Emit SocketIO event for real-time updates
            try:
                from app.services.socketio_manager import socketio_manager
                socketio_manager.emit_to_tenant(
                    task.tenant_id,
                    'task_progress',
                    {
                        'task_id': task.id,
                        'progress_percentage': progress_percentage,
                        'current_step': current_step,
                        'updated_at': task.last_progress_update.isoformat()
                    }
                )
            except Exception as e:
                print(f"[LONG_TASK] Error emitting progress event: {e}")

            return {
                'success': True,
                'progress': progress_percentage,
                'current_step': current_step
            }

        except Exception as e:
            print(f"[LONG_TASK] Error updating progress: {e}")
            return {'success': False, 'error': str(e)}

    def complete_task(
        self,
        task_id: int,
        result: Dict[str, Any],
        agent_id: int = None
    ) -> Dict[str, Any]:
        """
        Mark task as completed with results.

        Args:
            task_id: ID of completed task
            result: Execution result dictionary
            agent_id: Optional agent ID

        Returns:
            Result dictionary
        """
        task = Task.query.get(task_id)
        if not task:
            return {'success': False, 'error': 'Task not found'}

        try:
            # Update task
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            task.progress_percentage = 100
            task.execution_result = json.dumps(result)
            task.current_step = 'Completed'
            db.session.commit()

            # Create completion comment
            TaskComment.create_comment(
                task_id=task.id,
                comment_text=f"Task completed successfully",
                agent_id=agent_id,
                comment_type='status_change',
                is_system=True,
                meta_data=json.dumps({
                    'old_status': 'in_progress',
                    'new_status': 'completed'
                }),
                tenant_id=task.tenant_id
            )

            # Emit SocketIO event
            try:
                from app.services.socketio_manager import socketio_manager
                socketio_manager.emit_to_tenant(
                    task.tenant_id,
                    'task_completed',
                    {
                        'task_id': task.id,
                        'result': result,
                        'completed_at': task.completed_at.isoformat()
                    }
                )
            except Exception as e:
                print(f"[LONG_TASK] Error emitting completion event: {e}")

            # Send chat notification to user
            try:
                from app.models.message import Message
                agent = task.assigned_to_agent
                user = task.created_by

                if agent and user:
                    # Get room ID for this user-agent conversation
                    room_id = f"dm_{min(user.id, agent.id)}_{max(user.id, agent.id)}"

                    # Create notification message
                    summary = result.get('summary', 'Task completed successfully.')
                    notification_text = f"✅ Task completed: **{task.title}**\n\n{summary}\n\n[View full details →](/tasks/{task.id})"

                    message = Message(
                        sender_id=None,  # Agents don't have sender_id
                        recipient_id=user.id,
                        department_id=task.department_id,
                        content=notification_text,
                        agent_id=agent.id
                    )
                    db.session.add(message)
                    db.session.commit()

                    # Emit message via SocketIO
                    socketio_manager.emit_to_tenant(
                        task.tenant_id,
                        'new_message',
                        {
                            'room_id': room_id,
                            'message': {
                                'id': message.id,
                                'content': notification_text,
                                'sender': agent.name,
                                'sender_id': agent.id,
                                'agent_id': agent.id,
                                'created_at': message.created_at.isoformat(),
                                'is_user': False
                            }
                        }
                    )
                    print(f"[LONG_TASK] Sent completion notification to user {user.id}")
            except Exception as e:
                print(f"[LONG_TASK] Error sending chat notification: {e}")
                import traceback
                traceback.print_exc()

            return {
                'success': True,
                'message': 'Task completed',
                'result': result
            }

        except Exception as e:
            print(f"[LONG_TASK] Error completing task: {e}")
            return {'success': False, 'error': str(e)}

    def fail_task(
        self,
        task_id: int,
        error: str,
        agent_id: int = None,
        retry: bool = False
    ) -> Dict[str, Any]:
        """
        Mark task as failed with error details.

        Args:
            task_id: ID of failed task
            error: Error message
            agent_id: Optional agent ID
            retry: Whether to retry the task

        Returns:
            Result dictionary
        """
        task = Task.query.get(task_id)
        if not task:
            return {'success': False, 'error': 'Task not found'}

        try:
            # Update task
            task.execution_error = error
            task.retry_count = (task.retry_count or 0) + 1

            if not retry or task.retry_count >= 3:
                # Max retries reached or not retrying
                task.status = 'completed'  # Mark as completed (failed)
                task.completed_at = datetime.utcnow()

            db.session.commit()

            # Create error comment
            TaskComment.create_comment(
                task_id=task.id,
                comment_text=f"Task execution failed: {error}",
                agent_id=agent_id,
                comment_type='error',
                is_system=True,
                meta_data=json.dumps({
                    'error': error,
                    'retry_count': task.retry_count
                }),
                tenant_id=task.tenant_id
            )

            # Emit SocketIO event
            try:
                from app.services.socketio_manager import socketio_manager
                socketio_manager.emit_to_tenant(
                    task.tenant_id,
                    'task_failed',
                    {
                        'task_id': task.id,
                        'error': error,
                        'retry_count': task.retry_count
                    }
                )
            except Exception as e:
                print(f"[LONG_TASK] Error emitting failure event: {e}")

            return {
                'success': True,
                'message': 'Task marked as failed',
                'retry_count': task.retry_count
            }

        except Exception as e:
            print(f"[LONG_TASK] Error failing task: {e}")
            return {'success': False, 'error': str(e)}

    def _queue_task(self, task: Task, agent, user, plan: Dict) -> Optional[Job]:
        """
        Queue a task for background execution.

        Args:
            task: Task to queue
            agent: Agent that will execute
            user: User who created task
            plan: Execution plan

        Returns:
            RQ Job instance or None
        """
        try:
            # Determine queue based on priority
            if task.priority == 'urgent':
                queue = self.high_queue
                queue_name = 'high'
            elif task.priority in ['low', 'medium']:
                queue = self.low_queue
                queue_name = 'low'
            else:
                queue = self.default_queue
                queue_name = 'default'

            # Enqueue the task
            job = queue.enqueue(
                'app.workers.long_running_task_worker.execute_long_running_task',
                task_id=task.id,
                agent_id=agent.id,
                user_id=user.id,
                job_timeout=plan.get('estimated_duration_minutes', 30) * 60 + 300  # Add 5 min buffer
            )

            print(f"[LONG_TASK] Task {task.id} queued as job {job.id} in queue {queue_name}")

            # Update task with job info
            task.rq_job_id = job.id
            task.queue_name = queue_name
            task.status = 'in_progress'
            db.session.commit()

            # Create comment
            TaskComment.create_comment(
                task_id=task.id,
                comment_text=f"Task queued for execution in {queue_name} priority queue",
                agent_id=agent.id,
                comment_type='status_change',
                is_system=True,
                meta_data=json.dumps({
                    'job_id': job.id,
                    'queue': queue_name
                }),
                tenant_id=task.tenant_id
            )

            return job

        except Exception as e:
            print(f"[LONG_TASK] Error queueing task: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_plan_comment(self, task: Task, plan: Dict, agent) -> None:
        """
        Create a comment with the execution plan details.

        Args:
            task: Task instance
            plan: Execution plan dictionary
            agent: Agent that created the plan
        """
        try:
            # Format plan as readable text
            steps_text = "\n".join([
                f"{i+1}. {step['title']} ({step['estimated_duration_seconds']}s)"
                for i, step in enumerate(plan['steps'])
            ])

            comment_text = f"""📋 Execution Plan Created

**Estimated Duration:** {plan['estimated_duration_minutes']} minutes

**Steps:**
{steps_text}

**Approval Required:** {'Yes' if plan['requires_approval'] else 'No'}
{f"**Reason:** {plan['approval_reasoning']}" if plan['requires_approval'] else ''}

**Risks:** {', '.join(plan['risks']) if plan['risks'] else 'None identified'}
"""

            TaskComment.create_comment(
                task_id=task.id,
                comment_text=comment_text,
                agent_id=agent.id,
                comment_type='note',
                is_system=True,
                meta_data=json.dumps(plan),
                tenant_id=task.tenant_id
            )

        except Exception as e:
            print(f"[LONG_TASK] Error creating plan comment: {e}")


# Singleton instance
_long_running_task_service = None

def get_long_running_task_service() -> LongRunningTaskService:
    """Get or create the long running task service singleton"""
    global _long_running_task_service
    if _long_running_task_service is None:
        _long_running_task_service = LongRunningTaskService()
    return _long_running_task_service
