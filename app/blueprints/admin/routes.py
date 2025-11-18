"""
Admin routes for superadmin functionality
"""
from flask import render_template, current_app, request
from flask_login import login_required
from . import admin_bp
from app.utils.security_decorators import require_superadmin
from redis import Redis, ConnectionPool
from rq import Queue
from rq.job import Job
from rq.registry import (
    StartedJobRegistry,
    FinishedJobRegistry,
    FailedJobRegistry,
    ScheduledJobRegistry,
    DeferredJobRegistry
)
from datetime import datetime, timedelta


def get_redis_connection():
    """Create a fresh Redis connection with proper SSL handling"""
    redis_url = current_app.config['REDIS_URL']
    if redis_url.startswith('rediss://'):
        redis_url += '?ssl_cert_reqs=none'

    # Create connection with health check and retry
    return Redis.from_url(
        redis_url,
        socket_keepalive=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=10
    )


@admin_bp.route('/')
@login_required
@require_superadmin
def dashboard():
    """Admin dashboard home page with system overview"""
    try:
        # Get fresh Redis connection
        redis_conn = get_redis_connection()

        # Get all queues
        queue_names = ['default', 'enrichment', 'high', 'low']
        queues_data = []

        for queue_name in queue_names:
            queue = Queue(queue_name, connection=redis_conn)

            # Get registries for this queue
            started_registry = StartedJobRegistry(queue_name, connection=redis_conn)
            finished_registry = FinishedJobRegistry(queue_name, connection=redis_conn)
            failed_registry = FailedJobRegistry(queue_name, connection=redis_conn)
            scheduled_registry = ScheduledJobRegistry(queue_name, connection=redis_conn)
            deferred_registry = DeferredJobRegistry(queue_name, connection=redis_conn)

            queues_data.append({
                'name': queue_name,
                'count': len(queue),
                'started': len(started_registry),
                'finished': len(finished_registry),
                'failed': len(failed_registry),
                'scheduled': len(scheduled_registry),
                'deferred': len(deferred_registry)
            })

        # Get recent failed jobs across all queues
        recent_failures = []
        for queue_name in queue_names:
            failed_registry = FailedJobRegistry(queue_name, connection=redis_conn)
            failed_job_ids = failed_registry.get_job_ids(0, 10)

            for job_id in failed_job_ids:
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    recent_failures.append({
                        'id': job.id,
                        'queue': queue_name,
                        'func_name': job.func_name,
                        'failed_at': job.ended_at,
                        'exc_info': job.exc_info[:200] if job.exc_info else 'No error info'
                    })
                except:
                    pass

        # Sort by failure time
        recent_failures.sort(key=lambda x: x['failed_at'] if x['failed_at'] else datetime.min, reverse=True)
        recent_failures = recent_failures[:10]

        return render_template(
            'admin/dashboard.html',
            queues=queues_data,
            recent_failures=recent_failures
        )

    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        return render_template(
            'admin/dashboard.html',
            queues=[],
            recent_failures=[],
            error=str(e)
        )


@admin_bp.route('/jobs')
@login_required
@require_superadmin
def jobs():
    """Detailed job browser"""
    try:
        # Get fresh Redis connection
        redis_conn = get_redis_connection()
        queue_name = request.args.get('queue', 'default')
        registry_type = request.args.get('registry', 'queued')

        queue = Queue(queue_name, connection=redis_conn)

        # Get jobs based on registry type
        if registry_type == 'queued':
            job_ids = queue.job_ids
        elif registry_type == 'started':
            registry = StartedJobRegistry(queue_name, connection=redis_conn)
            job_ids = registry.get_job_ids()
        elif registry_type == 'finished':
            registry = FinishedJobRegistry(queue_name, connection=redis_conn)
            job_ids = registry.get_job_ids(0, 50)
        elif registry_type == 'failed':
            registry = FailedJobRegistry(queue_name, connection=redis_conn)
            job_ids = registry.get_job_ids(0, 50)
        elif registry_type == 'scheduled':
            registry = ScheduledJobRegistry(queue_name, connection=redis_conn)
            job_ids = registry.get_job_ids()
        else:
            job_ids = []

        # Fetch job details
        jobs_list = []
        for job_id in job_ids[:50]:  # Limit to 50 jobs
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                jobs_list.append({
                    'id': job.id,
                    'func_name': job.func_name,
                    'args': str(job.args)[:100],
                    'kwargs': str(job.kwargs)[:100],
                    'status': job.get_status(),
                    'created_at': job.created_at,
                    'started_at': job.started_at,
                    'ended_at': job.ended_at,
                    'exc_info': job.exc_info[:500] if job.exc_info else None
                })
            except:
                pass

        return render_template(
            'admin/jobs.html',
            jobs=jobs_list,
            queue=queue_name,
            registry=registry_type
        )

    except Exception as e:
        print(f"Error loading jobs: {e}")
        return render_template(
            'admin/jobs.html',
            jobs=[],
            queue='default',
            registry='queued',
            error=str(e)
        )


@admin_bp.route('/workers')
@login_required
@require_superadmin
def workers():
    """Worker status and management"""
    try:
        from rq import Worker
        # Get fresh Redis connection
        redis_conn = get_redis_connection()

        workers_list = []
        for worker in Worker.all(connection=redis_conn):
            workers_list.append({
                'name': worker.name,
                'state': worker.get_state(),
                'current_job': worker.get_current_job_id(),
                'successful_jobs': worker.successful_job_count,
                'failed_jobs': worker.failed_job_count,
                'total_working_time': worker.total_working_time,
                'birth_date': worker.birth_date,
                'last_heartbeat': worker.last_heartbeat
            })

        return render_template(
            'admin/workers.html',
            workers=workers_list
        )

    except Exception as e:
        print(f"Error loading workers: {e}")
        return render_template(
            'admin/workers.html',
            workers=[],
            error=str(e)
        )
