"""Check task 602 status"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.task import Task

app = create_app(os.getenv('FLASK_ENV', 'production'))

with app.app_context():
    task = Task.query.get(602)
    if task:
        print(f'Task 602:')
        print(f'  Title: {task.title}')
        print(f'  Status: {task.status}')
        print(f'  Assigned to agent: {task.assigned_to_agent_id}')
        print(f'  is_long_running: {task.is_long_running}')
        print(f'  requires_approval: {task.requires_approval}')
        print(f'  approval_status: {task.approval_status}')
    else:
        print('Task 602 not found')
