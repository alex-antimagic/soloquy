"""Reset task 602 to be reprocessed"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.task import Task

app = create_app(os.getenv('FLASK_ENV', 'production'))

with app.app_context():
    task = Task.query.get(602)
    if task:
        print(f'Resetting task 602...')
        print(f'  Before: is_long_running={task.is_long_running}')

        # Reset to unprocessed state
        task.is_long_running = None
        task.requires_approval = False
        task.approval_status = None
        task.execution_plan = None
        task.execution_model = None

        db.session.commit()

        print(f'  After: is_long_running={task.is_long_running}')
        print('✓ Task 602 reset successfully - will be processed on next CRON run')
    else:
        print('Task 602 not found')
