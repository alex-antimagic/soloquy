"""
Long Running Task Worker
Background worker that executes long-running agent tasks with progress tracking
"""
import json
import time
from typing import Dict, Any
from app import db
from app.models.task import Task
from app.models.agent import Agent
from app.models.user import User
from app.services.ai_service import get_ai_service
from app.services.long_running_task_service import get_long_running_task_service


def execute_long_running_task(task_id: int, agent_id: int, user_id: int) -> Dict[str, Any]:
    """
    Execute a long-running task in the background.
    This function runs in an RQ worker process.

    Args:
        task_id: ID of task to execute
        agent_id: ID of agent executing the task
        user_id: ID of user who created the task

    Returns:
        Execution result dictionary
    """
    print(f"[WORKER] Starting execution of task {task_id}")

    try:
        # Load models
        task = Task.query.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        agent = Agent.query.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Load execution plan
        if not task.execution_plan:
            raise ValueError("No execution plan found")

        plan = json.loads(task.execution_plan)
        print(f"[WORKER] Loaded execution plan with {len(plan['steps'])} steps")

        # Get services
        ai_service = get_ai_service()
        task_service = get_long_running_task_service()

        # Build system prompt for Sonnet
        system_prompt = _build_execution_system_prompt(agent, task, plan)

        # Execute steps with progress tracking
        all_messages = []
        step_results = []

        for i, step in enumerate(plan['steps']):
            step_num = step['step_number']
            progress = int((i / len(plan['steps'])) * 100)

            print(f"[WORKER] Executing step {step_num}: {step['title']}")

            # Update progress
            task_service.update_progress(
                task_id=task.id,
                progress_percentage=progress,
                current_step=f"Step {step_num}/{len(plan['steps'])}: {step['title']}",
                agent_id=agent.id
            )

            # Build prompt for this step
            step_prompt = f"""Execute step {step_num} of {len(plan['steps'])}:

**Step:** {step['title']}
**Description:** {step['description']}
**Estimated Duration:** {step['estimated_duration_seconds']} seconds

Please complete this step and provide:
1. What you did
2. The outcome/results
3. Any data or findings
4. Whether the step succeeded

Be thorough and detailed in your response."""

            # Execute step using Sonnet
            try:
                all_messages.append({
                    "role": "user",
                    "content": step_prompt
                })

                # Call AI with Sonnet model and agent's tools
                response = ai_service.chat(
                    messages=all_messages,
                    system_prompt=system_prompt,
                    model=task.execution_model or "claude-sonnet-4-5-20250929",
                    max_tokens=4096,
                    temperature=agent.temperature or 1.0,
                    agent=agent,
                    user=user
                )

                print(f"[WORKER] Step {step_num} response length: {len(response)} chars")

                # Store response
                all_messages.append({
                    "role": "assistant",
                    "content": response
                })

                step_results.append({
                    'step_number': step_num,
                    'title': step['title'],
                    'success': True,
                    'response': response
                })

                # Brief pause between steps to avoid rate limits
                if i < len(plan['steps']) - 1:
                    time.sleep(2)

            except Exception as step_error:
                print(f"[WORKER] Error in step {step_num}: {step_error}")
                step_results.append({
                    'step_number': step_num,
                    'title': step['title'],
                    'success': False,
                    'error': str(step_error)
                })

                # Decide whether to continue or abort
                if step.get('required', True):
                    raise Exception(f"Required step {step_num} failed: {step_error}")
                else:
                    # Optional step failed, continue
                    print(f"[WORKER] Optional step {step_num} failed, continuing...")

        # All steps completed
        print(f"[WORKER] All steps completed for task {task_id}")

        # Generate final summary
        summary_prompt = f"""All steps have been completed. Please provide a final summary:

1. Overall outcome and results
2. Key findings or deliverables
3. Any files generated or actions taken
4. Success status

Be concise but complete."""

        all_messages.append({
            "role": "user",
            "content": summary_prompt
        })

        final_response = ai_service.chat(
            messages=all_messages,
            system_prompt=system_prompt,
            model=task.execution_model or "claude-sonnet-4-5-20250929",
            max_tokens=2048,
            temperature=agent.temperature or 1.0,
            agent=agent,
            user=user
        )

        # Complete the task
        result = {
            'success': True,
            'steps_completed': len(step_results),
            'steps': step_results,
            'summary': final_response,
            'completed_at': time.time()
        }

        task_service.complete_task(
            task_id=task.id,
            result=result,
            agent_id=agent.id
        )

        print(f"[WORKER] Task {task_id} completed successfully")
        return result

    except Exception as e:
        print(f"[WORKER] Task {task_id} failed with error: {e}")
        import traceback
        traceback.print_exc()

        # Mark task as failed
        try:
            task_service = get_long_running_task_service()
            task_service.fail_task(
                task_id=task_id,
                error=str(e),
                agent_id=agent_id,
                retry=False  # Don't auto-retry for now
            )
        except Exception as fail_error:
            print(f"[WORKER] Error marking task as failed: {fail_error}")

        # Re-raise so RQ marks the job as failed
        raise


def _build_execution_system_prompt(agent, task, plan: Dict[str, Any]) -> str:
    """
    Build the system prompt for task execution.

    Args:
        agent: Agent model
        task: Task model
        plan: Execution plan dictionary

    Returns:
        System prompt string
    """
    # Get agent's base system prompt
    base_prompt = agent.system_prompt or f"You are {agent.name}, a helpful AI assistant."

    # Add task execution context
    execution_context = f"""

## TASK EXECUTION MODE

You are currently executing a long-running task in the background. This is a multi-step process.

**Task:** {task.title}
**Description:** {task.description or 'No additional description'}
**Estimated Duration:** {plan['estimated_duration_minutes']} minutes
**Number of Steps:** {len(plan['steps'])}

**Success Criteria:**
{chr(10).join(f"- {criterion}" for criterion in plan['success_criteria'])}

**Known Risks:**
{chr(10).join(f"- {risk}" for risk in plan['risks'])}

## EXECUTION GUIDELINES

1. **Follow the plan**: Complete each step thoroughly before moving to the next
2. **Be detailed**: Provide comprehensive results for each step
3. **Use your tools**: You have access to various tools - use them as needed
4. **Handle errors gracefully**: If a step encounters issues, explain what went wrong
5. **Stay focused**: Keep responses relevant to the current step
6. **Provide evidence**: When completing actions, describe what you did and the outcome

## PROGRESS TRACKING

Your progress is being tracked and displayed to the user in real-time. After completing each step, the system will automatically update the progress indicator.

## IMPORTANT

- This is a production task with real business impact
- Be thorough and accurate in your work
- Double-check critical actions before executing
- If you need clarification, state what information is unclear

Begin execution when prompted with the first step.
"""

    return base_prompt + execution_context


def test_worker_connection():
    """
    Test function to verify worker can connect to database and services.
    Can be called manually to test the worker setup.
    """
    print("[WORKER TEST] Testing worker connection...")

    try:
        # Test database connection
        task_count = Task.query.count()
        print(f"[WORKER TEST] Database connection OK - {task_count} tasks in database")

        # Test AI service
        ai_service = get_ai_service()
        print(f"[WORKER TEST] AI Service initialized OK")

        # Test task service
        task_service = get_long_running_task_service()
        print(f"[WORKER TEST] Task Service initialized OK")

        return {
            'success': True,
            'message': 'Worker connection test passed',
            'task_count': task_count
        }

    except Exception as e:
        print(f"[WORKER TEST] Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }
