from flask import render_template, request, jsonify, g, current_app, flash, abort
from flask_login import login_required, current_user
from app.blueprints.chat import chat_bp
from app.models.message import Message
from app.models.department import Department
from app.models.channel import Channel
from app.models.agent import Agent
from app.models.task import Task
from app.models.user import User
from app.services.ai_service import get_ai_service
from app.services.cloudinary_service import upload_image
from app import db, limiter, socketio
from app.utils.input_validators import validate_message_content, sanitize_ai_input
from app.utils.security_decorators import require_tenant_access
from datetime import datetime, timedelta
import json


@chat_bp.route('/')
@login_required
def index():
    """Chat interface"""
    return render_template('chat/index.html', title='Chat')


@chat_bp.route('/user/<int:user_id>')
@login_required
def user_chat(user_id):
    """Direct message with a user"""
    other_user = User.query.get_or_404(user_id)

    messages = Message.get_conversation(user1_id=current_user.id,
                                        user2_id=user_id,
                                        limit=100)

    # Get tasks for sidebar (only user's own tasks in user chat)
    user_tasks = Task.get_user_tasks(
        user_id=current_user.id,
        tenant_id=g.current_tenant.id,
        limit=5
    )

    return render_template('chat/direct_message.html',
                           title=f'@{other_user.full_name}',
                           is_agent=False,
                           recipient_id=other_user.id,
                           recipient_name=other_user.full_name,
                           recipient_subtitle='Direct Message',
                           recipient_is_online=other_user.is_online_now(),
                           recipient_avatar_url=other_user.avatar_url,
                           messages=messages,
                           user_tasks=user_tasks,
                           context_tasks=None)


@chat_bp.route('/agent/<int:agent_id>')
@login_required
def agent_chat(agent_id):
    """Direct message with an AI agent"""
    from app.models.agent import Agent
    agent = Agent.query.get_or_404(agent_id)

    # Verify agent belongs to current tenant
    if agent.department.tenant_id != g.current_tenant.id:
        return "Access denied", 403

    # Verify user has access to this agent
    if not agent.can_user_access(current_user):
        return "Access denied - you don't have permission to chat with this agent", 403

    # Get conversation history between THIS user and THIS agent
    # This maintains separate conversation threads - each user has their own chat with each agent
    messages = agent.get_conversation_with_user(
        user_id=current_user.id,
        limit=100
    )

    # Get tasks for sidebar
    user_tasks = Task.get_user_tasks(
        user_id=current_user.id,
        tenant_id=g.current_tenant.id,
        limit=5
    )

    # Get agent's assigned tasks
    agent_tasks = Task.query.filter_by(
        assigned_to_agent_id=agent.id,
        tenant_id=g.current_tenant.id
    ).filter(Task.status != 'completed').order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).limit(5).all()

    context_tasks = Task.get_department_tasks(
        department_id=agent.department_id,
        tenant_id=g.current_tenant.id,
        limit=5
    )

    return render_template('chat/direct_message.html',
                           title=agent.name,
                           is_agent=True,
                           recipient_id=agent.id,
                           recipient_name=agent.name,
                           recipient_subtitle=f'{agent.department.name} Department',
                           recipient_is_online=True,
                           agent_description=agent.description,
                           agent_avatar_url=agent.avatar_url,
                           department_id=agent.department_id,
                           messages=messages,
                           user_tasks=user_tasks,
                           agent_tasks=agent_tasks,
                           context_tasks=context_tasks,
                           context_department=agent.department,
                           context_agent=agent)


@chat_bp.route('/upload-image', methods=['POST'])
@login_required
def upload_chat_image():
    """Upload a file (image or document) for chat messages"""
    try:
        # Validate file upload - accept both 'image' and 'file' form fields for backwards compatibility
        file = request.files.get('image') or request.files.get('file')

        if not file:
            return jsonify({'error': 'No file provided'}), 400

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning

        max_size = current_app.config.get('MAX_FILE_SIZE', 10 * 1024 * 1024)
        if file_size > max_size:
            return jsonify({'error': f'File too large. Maximum size is {max_size // (1024 * 1024)}MB'}), 400

        # Validate file type
        allowed_extensions = current_app.config.get('ALLOWED_FILE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'csv', 'txt', 'doc', 'docx', 'xls', 'xlsx'})
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type. Allowed: images, PDFs, documents, spreadsheets'}), 400

        # Determine MIME type
        mime_types = {
            # Images
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            # Documents
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'txt': 'text/plain',
            'rtf': 'application/rtf',
            # Spreadsheets
            'csv': 'text/csv',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            # Presentations
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            # Code/Data
            'json': 'application/json',
            'xml': 'application/xml',
            'yaml': 'application/x-yaml',
            'yml': 'application/x-yaml',
            'md': 'text/markdown',
            'py': 'text/x-python',
            'js': 'text/javascript',
            'html': 'text/html',
            'css': 'text/css',
        }
        mime_type = mime_types.get(file_ext, 'application/octet-stream')

        # Check if it's an image
        is_image = file_ext in current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})

        # Upload to Cloudinary
        file.seek(0)
        if is_image:
            upload_result = upload_image(file, folder="chat_images")
        else:
            from app.services.cloudinary_service import upload_file
            upload_result = upload_file(file, folder="chat_files")

        return jsonify({
            'success': True,
            'url': upload_result['secure_url'],
            'filename': file.filename,
            'size': file_size,
            'type': mime_type,
            'is_image': is_image
        })

    except Exception as e:
        current_app.logger.error(f"Error uploading chat file: {str(e)}")
        return jsonify({'error': 'Failed to upload file. Please try again.'}), 500


@chat_bp.route('/send', methods=['POST'])
@login_required
def send_message():
    """Send a message"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data received'}), 400

    content = data.get('content', '')
    department_id = data.get('department_id')
    recipient_id = data.get('recipient_id')
    agent_id = data.get('agent_id')

    # Attachment data (if image was uploaded)
    attachment_url = data.get('attachment_url')
    attachment_type = data.get('attachment_type')
    attachment_filename = data.get('attachment_filename')
    attachment_size = data.get('attachment_size')

    # Validate message content (allow empty if there's an attachment)
    if not content and not attachment_url:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if content:
        is_valid, error = validate_message_content(content)
        if not is_valid:
            return jsonify({'error': error}), 400

    # Determine message type
    message_type = 'image' if attachment_url else 'text'

    # Save user's message
    message = Message(
        content=content or '(image)',
        sender_id=current_user.id,
        department_id=department_id,
        recipient_id=recipient_id,
        message_type=message_type,
        attachment_url=attachment_url,
        attachment_type=attachment_type,
        attachment_filename=attachment_filename,
        attachment_size=attachment_size
    )
    db.session.add(message)
    db.session.commit()

    # Broadcast user message via Socket.IO
    message_data = {
        'id': message.id,
        'content': message.content,
        'sender_id': current_user.id,
        'sender': current_user.full_name,
        'message_type': message.message_type,
        'created_at': message.created_at.isoformat()
    }

    # Include attachment data if present
    if message.attachment_url:
        message_data.update({
            'attachment_url': message.attachment_url,
            'attachment_type': message.attachment_type,
            'attachment_filename': message.attachment_filename,
            'attachment_size': message.attachment_size
        })

    if recipient_id:
        # User-to-user DM - create consistent conversation ID
        user_ids = sorted([current_user.id, recipient_id])
        conversation_id = f"user_{user_ids[0]}_{user_ids[1]}"
        socketio.emit('new_message', message_data, room=conversation_id)

        # Check if this is the first message in this conversation
        from app.models.user import User
        previous_messages = Message.get_conversation(user1_id=current_user.id, user2_id=recipient_id, limit=2)
        if len(previous_messages) == 1:  # Only this message exists
            # Notify recipient about new conversation
            recipient_room = f"user_{recipient_id}"
            recipient_user = User.query.get(recipient_id)
            if recipient_user:
                socketio.emit('new_conversation', {
                    'type': 'user',
                    'user_id': current_user.id,
                    'user_name': current_user.full_name,
                    'user_avatar': current_user.avatar_url,
                    'is_online': True,
                    'message_preview': content[:50] if content else '(image)'
                }, room=recipient_room)
    elif agent_id:
        # User-to-agent DM
        conversation_id = f"agent_{agent_id}_user_{current_user.id}"
        socketio.emit('new_message', message_data, room=conversation_id)
    elif department_id:
        # Department/Channel message - broadcast to all users in the channel
        from app.models.department import Department
        department = Department.query.get(department_id)
        if department:
            # Room name based on department ID
            department_room = f"department_{department_id}"
            socketio.emit('new_message', message_data, room=department_room)

    # If message is to an agent, generate AI response
    agent_response = None
    print(f"[SEND_MESSAGE] agent_id: {agent_id}, recipient_id: {recipient_id}, department_id: {department_id}")
    if agent_id:
        print(f"[SEND_MESSAGE] Querying for agent with ID: {agent_id}")
        agent = Agent.query.get(agent_id)
        print(f"[SEND_MESSAGE] Agent found: {agent}")
        if agent:
            print(f"[SEND_MESSAGE] Starting AI response generation for agent: {agent.name}")
            try:
                # Get conversation history between THIS user and THIS agent
                # This maintains separate conversation threads per user
                conversation_messages = agent.get_conversation_with_user(
                    user_id=current_user.id,
                    limit=20
                )

                # Build messages for Claude API
                api_messages = []
                for msg in conversation_messages:
                    if msg.sender_id == current_user.id:  # User message
                        # Build content array for multi-modal support
                        message_content = []

                        # Add attachment if present
                        if msg.attachment_url:
                            if msg.attachment_type and msg.attachment_type.startswith('image/'):
                                # For images, use vision API format
                                import requests
                                import base64
                                try:
                                    # Fetch image and convert to base64
                                    response = requests.get(msg.attachment_url, timeout=10)
                                    if response.status_code == 200:
                                        image_data = base64.b64encode(response.content).decode('utf-8')
                                        message_content.append({
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": msg.attachment_type,
                                                "data": image_data
                                            }
                                        })
                                except Exception as e:
                                    print(f"Error fetching image for vision: {e}")
                                    # Fall back to text description
                                    message_content.append({
                                        "type": "text",
                                        "text": f"[Image attached: {msg.attachment_filename or 'image'}]"
                                    })
                            else:
                                # For PDFs and documents, add text description
                                file_type = msg.attachment_type or 'file'
                                message_content.append({
                                    "type": "text",
                                    "text": f"[{file_type} file attached: {msg.attachment_filename}, URL: {msg.attachment_url}]"
                                })

                        # Add text content
                        if msg.content:
                            message_content.append({
                                "type": "text",
                                "text": msg.content
                            })

                        api_messages.append({
                            'role': 'user',
                            'content': message_content if message_content else msg.content
                        })
                    elif msg.agent_id == agent.id:  # Agent message
                        api_messages.append({
                            'role': 'assistant',
                            'content': msg.content
                        })

                # Add current message (with attachment if present)
                current_message_content = []

                if attachment_url:
                    if attachment_type and attachment_type.startswith('image/'):
                        # For images, use vision API format
                        import requests
                        import base64
                        try:
                            response = requests.get(attachment_url, timeout=10)
                            if response.status_code == 200:
                                image_data = base64.b64encode(response.content).decode('utf-8')
                                current_message_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": attachment_type,
                                        "data": image_data
                                    }
                                })
                        except Exception as e:
                            print(f"Error fetching image for vision: {e}")
                            current_message_content.append({
                                "type": "text",
                                "text": f"[Image attached: {attachment_filename or 'image'}]"
                            })
                    else:
                        # For PDFs and documents
                        file_type = attachment_type or 'file'
                        current_message_content.append({
                            "type": "text",
                            "text": f"[{file_type} file attached: {attachment_filename}, URL: {attachment_url}]"
                        })

                if content:
                    current_message_content.append({
                        "type": "text",
                        "text": content
                    })

                api_messages.append({
                    'role': 'user',
                    'content': current_message_content if current_message_content else content
                })

                # Fetch agent's assigned tasks (exclude completed)
                agent_tasks = Task.query.filter_by(
                    assigned_to_agent_id=agent.id,
                    tenant_id=g.current_tenant.id
                ).filter(Task.status != 'completed').all()

                # Get recently generated files (last 5 minutes)
                from app.models.generated_file import GeneratedFile
                recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
                recent_files = GeneratedFile.query.filter(
                    GeneratedFile.agent_id == agent.id,
                    GeneratedFile.user_id == current_user.id,
                    GeneratedFile.created_at >= recent_cutoff
                ).order_by(GeneratedFile.created_at.desc()).limit(10).all()

                # Build system prompt with tenant, user, task, and file context
                system_prompt = agent.build_system_prompt_with_context(
                    tenant=g.current_tenant,
                    user=current_user,
                    tasks=agent_tasks,
                    generated_files=recent_files
                )

                # Get AI response (with MCP context if enabled)
                # Use higher max_tokens for agents with file generation to avoid truncation
                max_tokens = 2048 if agent.enable_file_generation else 1024
                ai_service = get_ai_service()
                agent_response_text = ai_service.chat(
                    messages=api_messages,
                    system_prompt=system_prompt,
                    model=agent.model,              # Use agent's configured model
                    temperature=agent.temperature,   # Use agent's temperature
                    agent=agent,
                    user=current_user,
                    max_tokens=max_tokens
                )

                # Save agent's response
                agent_message = Message(
                    content=agent_response_text,
                    agent_id=agent.id,
                    department_id=department_id
                )
                db.session.add(agent_message)
                db.session.commit()

                # Link any recently generated files to this message
                from app.models.generated_file import GeneratedFile
                recent_cutoff = datetime.utcnow() - timedelta(seconds=30)
                generated_files = GeneratedFile.query.filter(
                    GeneratedFile.agent_id == agent.id,
                    GeneratedFile.user_id == current_user.id,
                    GeneratedFile.message_id == None,
                    GeneratedFile.created_at >= recent_cutoff
                ).all()

                for file in generated_files:
                    file.message_id = agent_message.id

                if generated_files:
                    db.session.commit()

                # Don't broadcast via Socket.IO - agent response is returned in HTTP response
                # to avoid duplicate messages in UI

                # Detect if agent mentioned any tasks using Haiku
                mentioned_tasks = []
                if agent_tasks:
                    try:
                        # Build task list for analysis
                        task_list = "\n".join([f"{i+1}. {task.title}" for i, task in enumerate(agent_tasks)])
                        detection_prompt = f"""Analyze the agent's response and determine which task(s) they are referring to or discussing.

Agent's tasks:
{task_list}

Agent's response:
{agent_response_text}

Return ONLY the task numbers (1, 2, 3, etc.) that the agent mentioned or addressed in their response, separated by commas. If no tasks were mentioned, return "none"."""

                        # Use Haiku for fast, cheap task detection
                        task_detection = ai_service.chat(
                            messages=[{'role': 'user', 'content': detection_prompt}],
                            system_prompt="You are a task detection assistant. Return only task numbers or 'none'.",
                            model='claude-haiku-4-5-20251001',
                            max_tokens=50,
                            temperature=0
                        ).strip().lower()

                        # Parse detected task numbers
                        if task_detection != 'none':
                            task_numbers = [int(n.strip()) for n in task_detection.split(',') if n.strip().isdigit()]
                            for task_num in task_numbers:
                                if 0 < task_num <= len(agent_tasks):
                                    task = agent_tasks[task_num - 1]
                                    mentioned_tasks.append({
                                        'id': task.id,
                                        'title': task.title,
                                        'description': task.description,
                                        'status': task.status,
                                        'priority': task.priority,
                                        'due_date': task.due_date.isoformat() if task.due_date else None,
                                        'is_overdue': task.is_overdue()
                                    })
                    except Exception as e:
                        print(f"Error detecting task mentions: {e}")
                        # Continue without task detection

                agent_response = {
                    'id': agent_message.id,
                    'content': agent_message.content,
                    'sender': agent.name,
                    'created_at': agent_message.created_at.isoformat(),
                    'mentioned_tasks': mentioned_tasks,
                    'generated_files': [{
                        'id': f.id,
                        'filename': f.filename,
                        'file_type': f.file_type,
                        'file_size': f.file_size,
                        'file_size_display': f.file_size_display,
                        'cloudinary_url': f.cloudinary_url,
                        'icon_class': f.icon_class
                    } for f in generated_files] if generated_files else []
                }
                print(f"[SEND_MESSAGE] Agent response created successfully. ID: {agent_message.id}, Files: {len(generated_files)}")

            except Exception as e:
                print(f"[SEND_MESSAGE] ERROR generating AI response: {e}")
                import traceback
                traceback.print_exc()
                # Continue without agent response

    response_data = {
        'id': message.id,
        'content': message.content,
        'sender': message.get_sender_name(),
        'created_at': message.created_at.isoformat()
    }

    print(f"[SEND_MESSAGE] agent_response exists: {agent_response is not None}")
    if agent_response:
        response_data['agent_response'] = agent_response
        print(f"[SEND_MESSAGE] Added agent_response to response_data")
    else:
        print(f"[SEND_MESSAGE] No agent_response to add")

    print(f"[SEND_MESSAGE] Returning response_data: {list(response_data.keys())}")
    return jsonify(response_data)


@chat_bp.route('/typing', methods=['POST'])
@login_required
def typing_indicator():
    """
    Broadcast typing indicator to other participants in conversation.

    Expected JSON payload:
        conversation_id: The conversation identifier
        is_typing: Boolean indicating if user is typing
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data received'}), 400

    conversation_id = data.get('conversation_id')
    is_typing = data.get('is_typing', False)

    if not conversation_id:
        return jsonify({'error': 'conversation_id is required'}), 400

    # Broadcast typing status to other participants via Socket.IO (exclude sender)
    socketio.emit('typing', {
        'user_id': current_user.id,
        'user_name': current_user.full_name,
        'is_typing': is_typing
    }, room=conversation_id)

    return jsonify({'success': True})


@chat_bp.route('/messages/<int:message_id>/read', methods=['POST'])
@login_required
def mark_message_read(message_id):
    """
    Mark a message as read by the current user.

    Args:
        message_id: ID of the message to mark as read
    """
    from datetime import datetime

    message = Message.query.get_or_404(message_id)

    # Don't mark own messages as read
    if message.sender_id == current_user.id:
        return jsonify({'success': True})

    # Mark as read
    message.mark_as_read(current_user.id)

    # Determine conversation ID for broadcasting
    conversation_id = None
    if message.recipient_id:
        # User-to-user DM
        user_ids = sorted([message.sender_id, message.recipient_id])
        conversation_id = f"user_{user_ids[0]}_{user_ids[1]}"
    elif message.agent_id:
        # User-to-agent
        conversation_id = f"agent_{message.agent_id}_user_{message.sender_id}"
    elif message.channel_id:
        # Channel message
        from app.models.channel import Channel
        channel = Channel.query.get(message.channel_id)
        if channel:
            conversation_id = f"channel_{channel.slug}"

    # Broadcast read receipt to sender via Socket.IO
    if conversation_id:
        socketio.emit('read_receipt', {
            'message_id': message_id,
            'user_id': current_user.id,
            'user_name': current_user.full_name,
            'read_at': datetime.utcnow().isoformat()
        }, room=conversation_id)

    return jsonify({'success': True})


# ========== CHANNEL ROUTES ==========

@chat_bp.route('/channel/<slug>')
@login_required
def channel_chat(slug):
    """Channel chat (includes department and custom channels)"""
    channel = Channel.query.filter_by(
        tenant_id=g.current_tenant.id,
        slug=slug
    ).first_or_404()

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        flash('You do not have access to this private channel.', 'danger')
        abort(403)

    # Get messages for this channel
    messages = Message.query.filter_by(
        channel_id=channel.id
    ).order_by(Message.created_at.asc()).limit(100).all()

    # Get associated agents (from department if channel is linked)
    associated_agents = channel.get_associated_agents()

    return render_template('chat/channel.html',
                          title=f'#{channel.name}',
                          channel=channel,
                          messages=messages,
                          associated_agents=associated_agents,
                          context_channel=channel,
                          context_department=channel.department)


@chat_bp.route('/channel/<slug>/mentions', methods=['GET'])
@login_required
@require_tenant_access
def get_channel_mentions(slug):
    """Get available users and agents for @ mentions in a channel"""
    channel = Channel.query.filter_by(
        tenant_id=g.current_tenant.id,
        slug=slug
    ).first_or_404()

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        abort(403)

    # Get all agents in tenant and filter by access control
    from app.models.user import User
    all_agents = Agent.query.join(Department).filter(
        Department.tenant_id == g.current_tenant.id
    ).all()

    # Filter agents based on access control
    agents = [agent for agent in all_agents if agent.can_user_access(current_user)]

    # Get all users in tenant
    users = User.query.join(User.tenant_memberships).filter_by(
        tenant_id=g.current_tenant.id
    ).all()

    # Build response
    suggestions = []

    # Add agents
    for agent in agents:
        suggestions.append({
            'type': 'agent',
            'id': agent.id,
            'name': agent.name,
            'display': f"@{agent.name}",
            'avatar': agent.avatar_url or f"https://ui-avatars.com/api/?name={agent.name}&background=0d6efd"
        })

    # Add users
    for user in users:
        if user.id != current_user.id:  # Don't include current user
            suggestions.append({
                'type': 'user',
                'id': user.id,
                'name': user.full_name,
                'display': f"@{user.full_name.replace(' ', '')}",
                'avatar': user.avatar_url or f"https://ui-avatars.com/api/?name={user.full_name}"
            })

    return jsonify({'suggestions': suggestions})


@chat_bp.route('/channels/create', methods=['POST'])
@login_required
def create_channel():
    """Create a new channel"""
    data = request.get_json()

    name = data.get('name', '').strip().lower()
    if not name:
        return jsonify({'error': 'Channel name is required'}), 400

    # Validate channel name (alphanumeric and hyphens only)
    import re
    if not re.match(r'^[a-z0-9-]+$', name):
        return jsonify({'error': 'Channel name can only contain lowercase letters, numbers, and hyphens'}), 400

    # Generate slug (same as name since we already validate it)
    slug = name

    # Check if channel with this slug already exists
    existing = Channel.query.filter_by(tenant_id=g.current_tenant.id, slug=slug).first()
    if existing:
        return jsonify({'error': 'A channel with this name already exists'}), 400

    # Create channel
    channel = Channel(
        tenant_id=g.current_tenant.id,
        name=name,
        slug=slug,
        description=data.get('description'),
        is_private=data.get('is_private', False),
        created_by_id=current_user.id
    )

    db.session.add(channel)
    db.session.commit()

    return jsonify({'success': True, 'slug': channel.slug, 'name': channel.name})


@chat_bp.route('/channel/<slug>/send', methods=['POST'])
@login_required
@require_tenant_access
def send_channel_message(slug):
    """Send a message to a channel with smart agent participation"""
    channel = Channel.query.filter_by(
        tenant_id=g.current_tenant.id,
        slug=slug
    ).first_or_404()

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        return jsonify({'error': 'You do not have access to this private channel'}), 403

    data = request.get_json()
    content = data.get('content', '').strip()

    # Attachment data (if file was uploaded)
    attachment_url = data.get('attachment_url')
    attachment_type = data.get('attachment_type')
    attachment_filename = data.get('attachment_filename')
    attachment_size = data.get('attachment_size')

    # Validate message content (allow empty if there's an attachment)
    if not content and not attachment_url:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if content:
        is_valid, error = validate_message_content(content)
        if not is_valid:
            return jsonify({'error': error}), 400

        # Sanitize AI input to prevent prompt injection
        is_safe, result = sanitize_ai_input(content)
        if not is_safe:
            return jsonify({'error': result}), 400

    # Determine message type
    message_type = 'image' if attachment_url else 'text'

    # Create user's message
    message = Message(
        channel_id=channel.id,
        sender_id=current_user.id,
        content=content or '(file)',
        message_type=message_type,
        attachment_url=attachment_url,
        attachment_type=attachment_type,
        attachment_filename=attachment_filename,
        attachment_size=attachment_size
    )
    db.session.add(message)
    db.session.commit()

    # Build message data for broadcast
    message_data = {
        'id': message.id,
        'content': message.content,
        'sender_id': current_user.id,
        'sender': current_user.full_name,
        'message_type': message.message_type,
        'created_at': message.created_at.isoformat()
    }

    # Include attachment data if present
    if message.attachment_url:
        message_data.update({
            'attachment_url': message.attachment_url,
            'attachment_type': message.attachment_type,
            'attachment_filename': message.attachment_filename,
            'attachment_size': message.attachment_size
        })

    # Broadcast user message via Socket.IO
    conversation_id = f"channel_{slug}"
    socketio.emit('new_message', message_data, room=conversation_id)

    # Parse mentions from the message
    mentions = message.parse_mentions()
    mentioned_agents = mentions['agents']

    # Store mentioned agent IDs
    if mentioned_agents:
        message.mentioned_agent_ids = [agent.id for agent in mentioned_agents]
        db.session.commit()

    # Get channel's associated agents
    associated_agents = channel.get_associated_agents()

    # Determine which agents should respond
    responding_agents = []

    # Only add explicitly mentioned agents (via @mentions)
    for agent in mentioned_agents:
        if agent not in responding_agents:
            responding_agents.append(agent)

    # Generate responses from agents
    agent_responses = []
    for agent in responding_agents:
        try:
            # Get channel conversation history
            channel_messages = Message.query.filter_by(
                channel_id=channel.id
            ).order_by(Message.created_at.desc()).limit(20).all()
            channel_messages.reverse()

            # Build API messages with multi-modal support
            api_messages = []
            for msg in channel_messages:
                if msg.sender_id:
                    message_content = []

                    # Add attachment if present
                    if msg.attachment_url:
                        if msg.attachment_type and msg.attachment_type.startswith('image/'):
                            # For images, use vision API format
                            import requests
                            import base64
                            try:
                                response = requests.get(msg.attachment_url, timeout=10)
                                if response.status_code == 200:
                                    image_data = base64.b64encode(response.content).decode('utf-8')
                                    message_content.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": msg.attachment_type,
                                            "data": image_data
                                        }
                                    })
                            except Exception as e:
                                print(f"Error fetching image for vision: {e}")
                                message_content.append({
                                    "type": "text",
                                    "text": f"[Image attached by {msg.sender.full_name}: {msg.attachment_filename or 'image'}]"
                                })
                        else:
                            # For PDFs and documents
                            file_type = msg.attachment_type or 'file'
                            message_content.append({
                                "type": "text",
                                "text": f"[{file_type} file attached by {msg.sender.full_name}: {msg.attachment_filename}, URL: {msg.attachment_url}]"
                            })

                    # Add text content with sender name
                    if msg.content:
                        message_content.append({
                            "type": "text",
                            "text": f"{msg.sender.full_name}: {msg.content}"
                        })

                    api_messages.append({
                        'role': 'user',
                        'content': message_content if message_content else f"{msg.sender.full_name}: "
                    })
                elif msg.agent_id:
                    api_messages.append({
                        'role': 'assistant',
                        'content': msg.content
                    })

            # Get recently generated files (last 5 minutes)
            from app.models.generated_file import GeneratedFile
            recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
            recent_files = GeneratedFile.query.filter(
                GeneratedFile.agent_id == agent.id,
                GeneratedFile.user_id == current_user.id,
                GeneratedFile.created_at >= recent_cutoff
            ).order_by(GeneratedFile.created_at.desc()).limit(10).all()

            # Build system prompt with channel context
            system_prompt = agent.build_system_prompt_with_context(
                tenant=g.current_tenant,
                user=current_user,
                tasks=[],
                generated_files=recent_files
            )
            system_prompt += f"\n\nYou are participating in the #{channel.name} channel."
            if channel.description:
                system_prompt += f"\nChannel description: {channel.description}"

            # Get AI response (with MCP context if enabled)
            # Use higher max_tokens for agents with file generation to avoid truncation
            max_tokens = 2048 if agent.enable_file_generation else 1024
            ai_service = get_ai_service()
            agent_response_text = ai_service.chat(
                messages=api_messages,
                system_prompt=system_prompt,
                model=agent.model,              # Use agent's configured model
                temperature=agent.temperature,   # Use agent's temperature
                agent=agent,
                user=current_user,
                max_tokens=max_tokens
            )

            # Save agent's response
            agent_message = Message(
                content=agent_response_text,
                agent_id=agent.id,
                channel_id=channel.id,
                message_type='text'
            )
            db.session.add(agent_message)
            db.session.commit()

            # Link any recently generated files to this message
            from app.models.generated_file import GeneratedFile
            recent_cutoff = datetime.utcnow() - timedelta(seconds=30)
            generated_files = GeneratedFile.query.filter(
                GeneratedFile.agent_id == agent.id,
                GeneratedFile.user_id == current_user.id,
                GeneratedFile.message_id == None,
                GeneratedFile.created_at >= recent_cutoff
            ).all()

            for file in generated_files:
                file.message_id = agent_message.id

            if generated_files:
                db.session.commit()

            # Broadcast agent response via Socket.IO
            message_data = {
                'id': agent_message.id,
                'content': agent_message.content,
                'agent_id': agent.id,
                'agent_name': agent.name,
                'message_type': 'text',
                'created_at': agent_message.created_at.isoformat(),
                'was_mentioned': agent in mentioned_agents
            }

            # Include generated files if any
            if generated_files:
                message_data['generated_files'] = [{
                    'id': f.id,
                    'filename': f.filename,
                    'file_type': f.file_type,
                    'file_size': f.file_size,
                    'file_size_display': f.file_size_display,
                    'cloudinary_url': f.cloudinary_url,
                    'icon_class': f.icon_class
                } for f in generated_files]

            socketio.emit('new_message', message_data, room=conversation_id)

            response_data = {
                'id': agent_message.id,
                'agent_id': agent.id,
                'agent_name': agent.name,
                'content': agent_message.content,
                'created_at': agent_message.created_at.isoformat(),
                'was_mentioned': agent in mentioned_agents
            }
            if generated_files:
                response_data['generated_files'] = [{
                    'id': f.id,
                    'filename': f.filename,
                    'file_type': f.file_type,
                    'file_size': f.file_size,
                    'file_size_display': f.file_size_display,
                    'cloudinary_url': f.cloudinary_url,
                    'icon_class': f.icon_class
                } for f in generated_files]

            agent_responses.append(response_data)

        except Exception as e:
            print(f"Error generating agent response for {agent.name}: {e}")
            continue

    return jsonify({
        'success': True,
        'message_id': message.id,
        'timestamp': message.created_at.isoformat(),
        'agent_responses': agent_responses
    })


# === Channel Management ===

@chat_bp.route('/channel/<slug>/description', methods=['POST'])
@login_required
def update_channel_description(slug):
    """Update channel description"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        return jsonify({'error': 'You do not have access to this private channel'}), 403

    # Check if user can edit (creator or admin)
    if channel.created_by_id != current_user.id:
        return jsonify({'error': 'Only the channel creator can edit the description'}), 403

    data = request.get_json()
    description = data.get('description', '').strip()

    # Update description
    channel.description = description if description else None
    db.session.commit()

    return jsonify({'success': True, 'description': channel.description})


# === Channel Member Management ===

@chat_bp.route('/channel/<slug>/members', methods=['GET'])
@login_required
def channel_members(slug):
    """View and manage channel members"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        abort(404)

    # Check if user can access this channel
    if not channel.can_user_access(current_user):
        abort(403)

    # Get all members who can access
    members = channel.get_members()

    # Get all tenant members for adding new ones (if channel is private)
    available_users = []
    if channel.is_private:
        available_users = [u for u in current_tenant.get_members() if u not in members]

    return render_template('chat/channel_members.html',
                          channel=channel,
                          members=members,
                          available_users=available_users)


@chat_bp.route('/channel/<slug>/members/add', methods=['POST'])
@login_required
def add_channel_member(slug):
    """Add a member to a private channel"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        return jsonify({'error': 'You do not have access to this private channel'}), 403

    # Only channel creator or admins can add members to private channels
    if not channel.is_private:
        return jsonify({'error': 'Cannot add members to public channels'}), 400

    if channel.created_by_id != current_user.id:
        return jsonify({'error': 'Only the channel creator can add members'}), 403

    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    # Verify user is in same tenant
    user = User.query.get(user_id)
    if not user or user not in g.current_tenant.get_members():
        return jsonify({'error': 'User not found'}), 404

    # Add member
    if channel.add_member(user):
        db.session.commit()
        return jsonify({'success': True, 'message': f'{user.full_name} added to channel'})

    return jsonify({'error': 'User is already a member'}), 400


@chat_bp.route('/channel/<slug>/members/remove', methods=['POST'])
@login_required
def remove_channel_member(slug):
    """Remove a member from a private channel"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        return jsonify({'error': 'You do not have access to this private channel'}), 403

    if not channel.is_private:
        return jsonify({'error': 'Cannot remove members from public channels'}), 400

    if channel.created_by_id != current_user.id:
        return jsonify({'error': 'Only the channel creator can remove members'}), 403

    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Cannot remove yourself if you're the creator
    if user.id == channel.created_by_id:
        return jsonify({'error': 'Channel creator cannot be removed'}), 400

    # Remove member
    if channel.remove_member(user):
        db.session.commit()
        return jsonify({'success': True, 'message': f'{user.full_name} removed from channel'})

    return jsonify({'error': 'User is not a member'}), 400


@chat_bp.route('/channel/<slug>/agents/add', methods=['POST'])
@login_required
def add_channel_agent(slug):
    """Add an agent to a channel"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        return jsonify({'error': 'You do not have access to this private channel'}), 403

    # Only channel creator can add agents
    if channel.created_by_id != current_user.id:
        return jsonify({'error': 'Only the channel creator can add agents'}), 403

    data = request.get_json()
    agent_id = data.get('agent_id')

    if not agent_id:
        return jsonify({'error': 'Agent ID is required'}), 400

    # Verify agent exists and belongs to this tenant
    from app.models.agent import Agent
    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

    # Verify agent belongs to a department in this tenant
    if agent.department.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Agent not found'}), 404

    # Add agent
    if channel.add_agent(agent):
        db.session.commit()
        return jsonify({'success': True, 'message': f'{agent.name} added to channel'})

    return jsonify({'error': 'Agent is already in this channel'}), 400


@chat_bp.route('/channel/<slug>/agents/remove', methods=['POST'])
@login_required
def remove_channel_agent(slug):
    """Remove an agent from a channel"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

    # Check if user has access to this channel
    if not channel.can_user_access(current_user):
        return jsonify({'error': 'You do not have access to this private channel'}), 403

    # Only channel creator can remove agents
    if channel.created_by_id != current_user.id:
        return jsonify({'error': 'Only the channel creator can remove agents'}), 403

    data = request.get_json()
    agent_id = data.get('agent_id')

    if not agent_id:
        return jsonify({'error': 'Agent ID is required'}), 400

    from app.models.agent import Agent
    agent = Agent.query.get(agent_id)
    if not agent:
        return jsonify({'error': 'Agent not found'}), 404

    # Remove agent
    if channel.remove_agent(agent):
        db.session.commit()
        return jsonify({'success': True, 'message': f'{agent.name} removed from channel'})

    return jsonify({'error': 'Agent is not in this channel'}), 400


@chat_bp.route('/unread-counts', methods=['GET'])
@login_required
def get_unread_counts():
    """Get unread message counts for all conversations (optimized)"""
    from sqlalchemy import func, and_, or_
    from app.models.read_receipt import ReadReceipt

    unread_counts = {}

    # Single optimized query: Get all unread messages with counts grouped by conversation
    # This replaces dozens of separate queries with one efficient query
    unread_messages = db.session.query(
        Message.channel_id,
        Message.agent_id,
        Message.sender_id,
        Message.recipient_id,
        func.count(Message.id).label('count')
    ).outerjoin(
        ReadReceipt,
        and_(
            ReadReceipt.message_id == Message.id,
            ReadReceipt.user_id == current_user.id
        )
    ).filter(
        ReadReceipt.id.is_(None),  # Only unread messages
        Message.sender_id != current_user.id,  # Don't count own messages
        or_(
            Message.channel_id.isnot(None),  # Channel messages
            and_(Message.agent_id.isnot(None), Message.sender_id.is_(None)),  # Agent messages
            Message.recipient_id == current_user.id  # DMs to current user
        )
    ).group_by(
        Message.channel_id,
        Message.agent_id,
        Message.sender_id,
        Message.recipient_id
    ).all()

    # Process results: Group by conversation type
    for msg in unread_messages:
        if msg.channel_id:
            # Channel message
            channel = Channel.query.get(msg.channel_id)
            if channel and channel.tenant_id == g.current_tenant.id:
                key = f'channel_{channel.slug}'
                unread_counts[key] = unread_counts.get(key, 0) + msg.count
        elif msg.agent_id:
            # Agent message
            key = f'agent_{msg.agent_id}'
            unread_counts[key] = unread_counts.get(key, 0) + msg.count
        elif msg.sender_id and msg.recipient_id == current_user.id:
            # User DM
            key = f'user_{msg.sender_id}'
            unread_counts[key] = unread_counts.get(key, 0) + msg.count

    return jsonify(unread_counts)


@chat_bp.route('/mark-read', methods=['POST'])
@login_required
def mark_messages_read():
    """Mark all messages in a conversation as read"""
    data = request.get_json()
    conversation_type = data.get('type')  # 'channel', 'agent', or 'user'
    conversation_id = data.get('id')

    if not conversation_type or not conversation_id:
        return jsonify({'error': 'type and id are required'}), 400

    try:
        if conversation_type == 'channel':
            # Mark all channel messages as read
            channel = Channel.query.filter_by(
                slug=conversation_id,
                tenant_id=g.current_tenant.id
            ).first()
            if not channel:
                return jsonify({'error': 'Channel not found'}), 404

            messages = Message.query.filter_by(
                channel_id=channel.id
            ).filter(Message.sender_id != current_user.id).all()

            for message in messages:
                if not message.is_read_by(current_user.id):
                    message.mark_as_read(current_user.id)

        elif conversation_type == 'agent':
            # Mark all agent messages as read
            agent_id = int(conversation_id)
            messages = Message.query.filter_by(
                agent_id=agent_id,
                sender_id=current_user.id
            ).all()

            for message in messages:
                if not message.is_read_by(current_user.id):
                    message.mark_as_read(current_user.id)

        elif conversation_type == 'user':
            # Mark all user DM messages as read
            other_user_id = int(conversation_id)
            messages = Message.query.filter_by(
                sender_id=other_user_id,
                recipient_id=current_user.id
            ).all()

            for message in messages:
                if not message.is_read_by(current_user.id):
                    message.mark_as_read(current_user.id)

        else:
            return jsonify({'error': 'Invalid conversation type'}), 400

        return jsonify({'success': True, 'marked': len(messages)})

    except Exception as e:
        print(f"Error marking messages as read: {e}")
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/message/<int:message_id>/convert-to-task', methods=['POST'])
@login_required
@require_tenant_access
def convert_message_to_task(message_id):
    """Convert an agent message to a task"""
    try:
        # Get the message
        message = Message.query.get_or_404(message_id)

        # Verify user has access to this message
        if message.department.tenant_id != g.current_tenant.id:
            return jsonify({'error': 'Access denied'}), 403

        # Only allow converting agent messages
        if not message.agent_id:
            return jsonify({'error': 'Only agent messages can be converted to tasks'}), 400

        # Get request data
        data = request.get_json() or {}

        # Get agent
        agent = message.agent

        # Use AI to generate proper task title and description
        content = message.content.strip()
        try:
            from app.services.ai_service import get_ai_service
            ai_service = get_ai_service()

            # Use Haiku for fast, cheap extraction
            extraction_result = ai_service.chat(
                messages=[{
                    'role': 'user',
                    'content': f"""Extract a task from this agent message. Generate:
1. A short, descriptive task title (max 80 chars) that captures the main action/deliverable
2. A comprehensive description with all relevant context, instructions, and details

Agent message:
{content}

Respond in JSON format:
{{"title": "short descriptive title", "description": "comprehensive description with all context"}}"""
                }],
                model='claude-haiku-3-5-20241022',
                temperature=0.2,
                max_tokens=500
            )

            # Parse JSON response
            import json
            import re

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', extraction_result)
            if json_match:
                extracted = json.loads(json_match.group())
                title = extracted.get('title', content.split('\n')[0][:100])[:100]
                description = extracted.get('description', content)
            else:
                # Fallback to simple extraction
                title = content.split('\n')[0][:100]
                description = content

        except Exception as ai_error:
            print(f"[CONVERT_TO_TASK] AI extraction error: {ai_error}")
            # Fallback to simple extraction
            title = content.split('\n')[0][:100] if content else 'Task from agent message'
            if len(title) < 10:
                import re
                sentences = re.split(r'[.!?]+', content)
                title = sentences[0][:100] if sentences else title
            description = content if len(content) > len(title) else None

        # Create task
        task = Task(
            title=title,
            description=description,
            priority=data.get('priority', 'medium'),
            status='pending',
            tenant_id=g.current_tenant.id,
            created_by_id=current_user.id,
            department_id=message.department_id,
            assigned_to_agent_id=agent.id if data.get('assign_to_agent', True) else None
        )

        db.session.add(task)
        db.session.commit()

        # Don't run detection here - let the CRON task processor handle it
        # This ensures all manually-created agent tasks go through the same workflow

        return jsonify({
            'success': True,
            'task_id': task.id,
            'task_title': task.title,
            'message': 'Task created successfully. It will be processed by the scheduler within 10 minutes.'
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error converting message to task: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
