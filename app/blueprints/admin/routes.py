"""
Admin routes for superadmin functionality
"""
from flask import render_template, current_app, request
from flask_login import login_required
from . import admin_bp
from app.utils.security_decorators import require_superadmin
from redis import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
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
import time

# Global connection pool - created once and reused
_redis_pool = None


def get_connection_pool():
    """Get or create the Redis connection pool"""
    global _redis_pool

    if _redis_pool is None:
        redis_url = current_app.config['REDIS_URL']
        if redis_url.startswith('rediss://'):
            redis_url += '?ssl_cert_reqs=none'

        # Create a connection pool with robust settings
        _redis_pool = ConnectionPool.from_url(
            redis_url,
            max_connections=10,
            socket_keepalive=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=10
        )

    return _redis_pool


def get_redis_connection():
    """Get a validated Redis connection from the pool"""
    pool = get_connection_pool()
    redis_conn = Redis(connection_pool=pool)

    # Validate connection with ping
    try:
        redis_conn.ping()
    except (RedisError, RedisConnectionError) as e:
        print(f"Redis connection validation failed: {e}")
        # Try to recreate the pool
        global _redis_pool
        _redis_pool = None
        pool = get_connection_pool()
        redis_conn = Redis(connection_pool=pool)

    return redis_conn


def retry_redis_operation(operation, max_retries=3, backoff_base=0.5):
    """
    Retry a Redis operation with exponential backoff

    Args:
        operation: A callable that performs the Redis operation
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay in seconds for exponential backoff

    Returns:
        The result of the operation, or None if all retries fail
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except (RedisError, RedisConnectionError) as e:
            if attempt == max_retries - 1:
                print(f"Redis operation failed after {max_retries} attempts: {e}")
                raise

            # Exponential backoff: 0.5s, 1s, 2s
            delay = backoff_base * (2 ** attempt)
            print(f"Redis operation failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}")
            time.sleep(delay)

            # Reset connection pool on error
            global _redis_pool
            _redis_pool = None


@admin_bp.route('/')
@login_required
@require_superadmin
def dashboard():
    """Admin dashboard home page with system overview"""
    try:
        def fetch_dashboard_data():
            """Wrapped operation for retry logic"""
            # Get Redis connection from pool
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

            return queues_data, recent_failures

        # Execute with retry logic
        queues_data, recent_failures = retry_redis_operation(fetch_dashboard_data)

        return render_template(
            'admin/dashboard.html',
            queues=queues_data,
            recent_failures=recent_failures
        )

    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        import traceback
        traceback.print_exc()
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
    queue_name = request.args.get('queue', 'default')
    registry_type = request.args.get('registry', 'queued')

    try:
        def fetch_jobs_data():
            """Wrapped operation for retry logic"""
            redis_conn = get_redis_connection()
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

            return jobs_list

        jobs_list = retry_redis_operation(fetch_jobs_data)

        return render_template(
            'admin/jobs.html',
            jobs=jobs_list,
            queue=queue_name,
            registry=registry_type
        )

    except Exception as e:
        print(f"Error loading jobs: {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            'admin/jobs.html',
            jobs=[],
            queue=queue_name,
            registry=registry_type,
            error=str(e)
        )


@admin_bp.route('/workers')
@login_required
@require_superadmin
def workers():
    """Worker status and management"""
    try:
        def fetch_workers_data():
            """Wrapped operation for retry logic"""
            from rq import Worker
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

            return workers_list

        workers_list = retry_redis_operation(fetch_workers_data)

        return render_template(
            'admin/workers.html',
            workers=workers_list
        )

    except Exception as e:
        print(f"Error loading workers: {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            'admin/workers.html',
            workers=[],
            error=str(e)
        )
