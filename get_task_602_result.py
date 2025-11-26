"""Get task 602 execution result and deliverables"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.task import Task

app = create_app(os.getenv('FLASK_ENV', 'production'))

with app.app_context():
    task = Task.query.get(602)
    if not task:
        print('Task 602 not found')
        sys.exit(1)

    print(f'Task 602: {task.title}')
    print(f'Status: {task.status}')
    print(f'\n' + '='*80)

    if task.execution_result:
        result = json.loads(task.execution_result)

        print('\n📋 EXECUTION SUMMARY:')
        print('='*80)
        print(result.get('summary', 'No summary available'))

        print('\n\n📦 STEPS COMPLETED:')
        print('='*80)
        steps = result.get('steps', [])
        for i, step in enumerate(steps, 1):
            print(f"\n{i}. {step.get('title', 'Unknown step')}")
            print(f"   Success: {step.get('success', False)}")
            if step.get('response'):
                response = step['response'][:200] + '...' if len(step['response']) > 200 else step['response']
                print(f"   Response: {response}")

        print(f'\n\n✅ Total steps completed: {result.get("steps_completed", 0)}')
    else:
        print('No execution result available')
