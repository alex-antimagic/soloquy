"""Manually send completion notification for task 602"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.task import Task
from app.models.message import Message
from app.services.socketio_manager import socketio_manager

app = create_app(os.getenv('FLASK_ENV', 'production'))

with app.app_context():
    task = Task.query.get(602)
    if not task:
        print('Task 602 not found')
        sys.exit(1)

    print(f'Task 602: {task.title}')
    print(f'Status: {task.status}')

    agent = task.assigned_to_agent
    user = task.created_by

    if not agent or not user:
        print('Agent or user not found')
        sys.exit(1)

    # Get room ID for this user-agent conversation
    room_id = f"dm_{min(user.id, agent.id)}_{max(user.id, agent.id)}"
    print(f'Room ID: {room_id}')

    # Get execution result
    try:
        result = json.loads(task.execution_result) if task.execution_result else {}
    except:
        result = {}

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

    print(f'✓ Created message {message.id} in room {room_id}')
    print(f'Notification sent to user {user.id} ({user.full_name})')

    # Emit message via SocketIO
    try:
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
        print('✓ Emitted SocketIO event')
    except Exception as e:
        print(f'⚠ Failed to emit SocketIO: {e}')
