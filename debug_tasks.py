#!/usr/bin/env python3
from app import create_app, db
from app.models.message import Message

app = create_app()
with app.app_context():
    # Get the most recent agent message
    msg = Message.query.filter(Message.agent_id.isnot(None)).order_by(Message.created_at.desc()).first()
    if msg:
        print('=== MESSAGE CONTENT ===')
        print(repr(msg.content))
        print()
        print('=== PARSED TASK SUGGESTIONS ===')
        suggestions = msg.parse_task_suggestions()
        print(f'Found {len(suggestions)} suggestions')
        for i, task in enumerate(suggestions):
            print(f'Task {i+1}:', task)
        print()
        print('=== CLEAN CONTENT ===')
        print(repr(msg.get_content_without_task_suggestions()))
    else:
        print('No agent messages found')
