"""
Cleanup script to delete all agent tasks
Run this ONCE before enabling the CRON processor to clear backlog
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.task import Task

app = create_app(os.getenv('FLASK_ENV', 'production'))

def cleanup_agent_tasks():
    """Delete all tasks assigned to agents"""
    with app.app_context():
        # Find all tasks assigned to agents
        agent_tasks = Task.query.filter(
            Task.assigned_to_agent_id.isnot(None)
        ).all()

        print(f"Found {len(agent_tasks)} tasks assigned to agents")

        if len(agent_tasks) == 0:
            print("No agent tasks to delete")
            return

        # Ask for confirmation
        print("\nThis will DELETE the following tasks:")
        for task in agent_tasks[:10]:  # Show first 10
            print(f"  - Task {task.id}: {task.title} (status: {task.status})")

        if len(agent_tasks) > 10:
            print(f"  ... and {len(agent_tasks) - 10} more")

        confirm = input(f"\nAre you sure you want to delete ALL {len(agent_tasks)} agent tasks? (yes/no): ")

        if confirm.lower() != 'yes':
            print("Cancelled - no tasks deleted")
            return

        # Delete all agent tasks
        for task in agent_tasks:
            db.session.delete(task)

        db.session.commit()
        print(f"\n✓ Successfully deleted {len(agent_tasks)} agent tasks")

if __name__ == '__main__':
    print("Agent Task Cleanup Script")
    print("=" * 50)
    cleanup_agent_tasks()
