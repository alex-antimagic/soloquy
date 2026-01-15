# Long-Running Agent Tasks System

## Overview

This system enables AI agents to detect, plan, and execute complex tasks that take more than 20 seconds to complete. It provides automatic detection, approval workflows, background execution, and real-time progress tracking.

## Architecture

### Detection Flow
1. **User creates task** assigned to an agent
2. **Haiku analyzes** task complexity (fast, <3s, cost-effective)
3. **If long-running detected** → Sonnet generates detailed execution plan
4. **Agent determines** if approval needed based on risk assessment
5. **Task queued** to RQ worker (if approved or no approval needed)
6. **Sonnet executes** with step-by-step progress tracking
7. **User notified** via SocketIO and task status

### Components

#### 1. Database Models
- **Task** - Extended with 17 long-running fields
  - `is_long_running`, `execution_plan`, `execution_model`
  - `rq_job_id`, `queue_name`, `progress_percentage`
  - `requires_approval`, `approval_status`, `approved_by_id`
  - `execution_result`, `execution_error`, `retry_count`

- **TaskComment** - Audit trail system
  - Supports both user and agent comments
  - System-generated comments for automation
  - Comment types: note, progress_update, status_change, approval, error

#### 2. AI Service Methods (`app/services/ai_service.py`)
- `detect_long_running_task()` - Uses Haiku for fast detection
- `generate_execution_plan()` - Uses Sonnet for planning

#### 3. Orchestration Service (`app/services/long_running_task_service.py`)
- `detect_and_handle()` - Main workflow coordinator
- `approve_task()` / `reject_task()` - Approval management
- `update_progress()` - Real-time progress with SocketIO
- `complete_task()` / `fail_task()` - Result handling

#### 4. Background Worker (`app/workers/long_running_task_worker.py`)
- `execute_long_running_task()` - Step-by-step execution with Sonnet
- Full access to agent tools (Outlook, file generation, website builder)
- Progress updates between steps
- Comprehensive error handling

#### 5. API Endpoints (`app/blueprints/tasks/routes.py`)
- `POST /tasks/<id>/approve` - Approve task for execution
- `POST /tasks/<id>/reject` - Reject task with reason
- `GET /tasks/<id>/progress` - Get current progress
- `GET/POST /tasks/<id>/comments` - Comment system
- `GET /tasks/<id>/execution-plan` - View detailed plan

#### 6. Frontend UI (`app/templates/tasks/view.html`)
- Execution plan viewer with steps, risks, success criteria
- Progress bar with real-time updates
- Approve/reject buttons for pending approvals
- Comments section with audit trail
- SocketIO listeners for instant updates
- Polling fallback (5s interval) for progress

## Configuration

### Environment Variables
```bash
# Already configured in your .env:
ANTHROPIC_API_KEY=your_key_here
REDIS_URL=redis://localhost:6379/0  # or Heroku Redis URL
```

### RQ Queues
- **high** - Urgent priority tasks
- **default** - Normal priority tasks
- **low** - Low priority tasks
- **enrichment** - Background data enrichment

## Deployment to Heroku

### 1. Database Migration
```bash
# Run locally first to test
export FLASK_APP=run.py
./venv/bin/flask db upgrade

# Deploy migrations to Heroku
git add .
git commit -m "Add long-running task system with migrations"
git push heroku main

# Run migrations on Heroku
heroku run flask db upgrade
```

### 2. Start RQ Worker Dyno

Add to your `Procfile`:
```
web: gunicorn run:app --worker-class eventlet -w 1
worker: python worker.py
```

Scale up the worker:
```bash
heroku ps:scale worker=1
```

Verify worker is running:
```bash
heroku ps
heroku logs --tail --dyno worker
```

### 3. Verify Redis Connection
```bash
# Check Redis is provisioned
heroku addons | grep redis

# If not provisioned, add it:
heroku addons:create heroku-redis:mini

# Test connection
heroku run python -c "from redis import Redis; import os; r = Redis.from_url(os.environ['REDIS_URL']); print(r.ping())"
```

## Testing

### 1. Test Detection (Local)
```bash
# Start Flask app
export FLASK_APP=run.py
./venv/bin/flask run

# Start RQ worker in separate terminal
export FLASK_APP=run.py
python worker.py

# Start Redis if not running
redis-server
```

### 2. Create Test Task
1. Log into worklead
2. Navigate to Tasks
3. Create a new task:
   - **Title**: "Generate quarterly sales report with charts"
   - **Description**: "Analyze Q4 sales data, create comparison charts, and generate PDF report"
   - **Assign to**: Any agent with file generation enabled
4. Submit the task

### 3. Verify Detection
Check logs for:
```
[TASK CREATE] Long-running detection result: {'is_long_running': True, ...}
[LONG_TASK] Detecting if task X is long-running...
[LONG_TASK] Detection result: {'is_long_running': True, 'estimated_duration_seconds': 45, ...}
[LONG_TASK] Task is long-running. Generating execution plan...
```

### 4. Test Approval Workflow
1. Navigate to task detail page
2. Verify "Approval Required" banner appears
3. Click "View Execution Plan" - should show steps, risks, criteria
4. Click "Approve" button
5. Verify task queued and progress bar appears

### 5. Monitor Execution
Watch RQ worker logs:
```
[WORKER] Starting execution of task X
[WORKER] Loaded execution plan with N steps
[WORKER] Executing step 1: ...
[WORKER] Step 1 response length: ...
[WORKER] All steps completed for task X
[WORKER] Task X completed successfully
```

Watch Flask app logs for progress updates:
```
[LONG_TASK] Task X queued as job Y in queue default
Progress update: {'task_id': X, 'progress_percentage': 25, ...}
```

### 6. Verify Frontend Updates
1. Open task detail page
2. Progress bar should update automatically
3. Current step should change as work progresses
4. Comments section should show system-generated updates
5. On completion, page reloads with success message

## Approval Logic

### Tasks Requiring Approval
- Modify critical business data (financial, customer)
- Send external communications (emails, API calls)
- Make irreversible changes (deletions, deployments)
- Involve sensitive information or compliance
- Have high business impact or cost

### Tasks NOT Requiring Approval
- Read-only analysis and reporting
- Internal document generation
- Data aggregation and visualization
- Research and information gathering
- Development/testing in non-production

## Cost Optimization

### Model Usage
- **Haiku** for detection (~$0.001 per task, <3 seconds)
- **Sonnet** for planning (~$0.015 per task, <10 seconds)
- **Sonnet** for execution (cost varies by task complexity)

### Example Cost Breakdown
**Simple Report Task (2 minutes)**:
- Detection: $0.001
- Planning: $0.015
- Execution: $0.05
- **Total**: ~$0.066

**Complex Multi-Step Task (15 minutes)**:
- Detection: $0.001
- Planning: $0.015
- Execution: $0.30
- **Total**: ~$0.316

## Monitoring & Debugging

### Check RQ Queue Status
```bash
# Locally
redis-cli
> LLEN rq:queue:default
> LLEN rq:queue:high
> LLEN rq:queue:low

# On Heroku
heroku redis:cli
> LLEN rq:queue:default
```

### View Failed Jobs
```python
from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry

redis_conn = Redis.from_url(os.environ['REDIS_URL'])
queue = Queue('default', connection=redis_conn)
registry = FailedJobRegistry(queue=queue)

for job_id in registry.get_job_ids():
    job = queue.fetch_job(job_id)
    print(f"Failed Job: {job_id}")
    print(f"Error: {job.exc_info}")
```

### Check Task Status via API
```bash
# Get task progress
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-app.herokuapp.com/tasks/123/progress

# Get task comments
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-app.herokuapp.com/tasks/123/comments
```

## Troubleshooting

### Worker Not Processing Jobs
1. Check worker is running: `heroku ps | grep worker`
2. Check Redis connection: `heroku redis:info`
3. Check worker logs: `heroku logs --tail --dyno worker`
4. Restart worker: `heroku ps:restart worker`

### Tasks Stuck in "Pending Approval"
1. Verify approval_status field: Should be 'pending'
2. Check if approve button appears in UI
3. Manually approve via API if needed

### Progress Not Updating
1. Check SocketIO connection in browser console
2. Verify SocketIO server is running
3. Check polling fallback is working (5s interval)
4. Verify update_progress() is being called in worker

### Execution Errors
1. Check task.execution_error field
2. Review worker logs for stack traces
3. Check agent tools are properly configured
4. Verify API keys (Anthropic, Outlook, etc.) are set

## Future Enhancements

### Potential Improvements
1. **Pause/Resume** - Allow pausing long-running tasks
2. **Step Retry** - Retry individual failed steps
3. **Parallel Steps** - Execute independent steps in parallel
4. **Cost Tracking** - Track token usage per task
5. **Email Notifications** - Send email when task completes
6. **Webhook Integration** - Trigger external systems on completion
7. **Task Templates** - Pre-defined plans for common tasks
8. **Resource Limits** - Set max duration, max tokens, etc.

## Files Modified/Created

### Backend
- `app/models/task.py` - Added 17 long-running fields
- `app/models/task_comment.py` - NEW - Audit trail model
- `app/services/ai_service.py` - Added detection and planning methods
- `app/services/long_running_task_service.py` - NEW - Orchestration service
- `app/workers/long_running_task_worker.py` - NEW - Background worker
- `app/blueprints/tasks/routes.py` - Added 5 new endpoints, detection integration

### Frontend
- `app/templates/tasks/view.html` - Added long-running UI, progress tracking, SocketIO

### Database
- `migrations/versions/4cd00bb095e0_add_long_running_task_fields.py`
- `migrations/versions/c1d81e327972_add_task_comments_table.py`

## Support

For issues or questions:
1. Check Heroku logs: `heroku logs --tail`
2. Check worker logs: `heroku logs --tail --dyno worker`
3. Review this documentation
4. Check task comments for error details

---

**Status**: ✅ Implementation complete, ready for testing and deployment
**Last Updated**: November 25, 2025
