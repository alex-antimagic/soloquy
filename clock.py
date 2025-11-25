"""
Scheduler for periodic tasks
Run with: python clock.py

For Heroku Scheduler, use individual commands:
- python clock.py process_tasks
- python clock.py cleanup_stale
"""
import sys
import os

# Ensure the application is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db

# Create Flask application
app = create_app(os.getenv('FLASK_ENV', 'production'))


def run_task_processor():
    """Process pending agent tasks"""
    with app.app_context():
        from app.workers.task_processor_job import process_pending_agent_tasks
        result = process_pending_agent_tasks()
        print(f"\n[SCHEDULER] Task Processor Result: {result}")
        return result


def run_task_cleanup():
    """Cleanup stale tasks"""
    with app.app_context():
        from app.workers.task_processor_job import cleanup_stale_tasks
        result = cleanup_stale_tasks()
        print(f"\n[SCHEDULER] Task Cleanup Result: {result}")
        return result


def run_maintenance():
    """Run full maintenance (both processor and cleanup)"""
    with app.app_context():
        from app.workers.task_processor_job import periodic_task_maintenance
        result = periodic_task_maintenance()
        print(f"\n[SCHEDULER] Maintenance Result: {result}")
        return result


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'maintenance'

    if command == 'process_tasks':
        print("[SCHEDULER] Running task processor...")
        run_task_processor()
    elif command == 'cleanup_stale':
        print("[SCHEDULER] Running stale task cleanup...")
        run_task_cleanup()
    elif command == 'maintenance':
        print("[SCHEDULER] Running full maintenance...")
        run_maintenance()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: process_tasks, cleanup_stale, maintenance")
        sys.exit(1)

    print("[SCHEDULER] Job completed successfully")
