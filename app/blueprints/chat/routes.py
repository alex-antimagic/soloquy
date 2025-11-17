from flask import render_template, request, jsonify, g, current_app
from flask_login import login_required, current_user
from app.blueprints.chat import chat_bp
from app.models.message import Message
from app.models.department import Department
from app.models.channel import Channel
from app.models.agent import Agent
from app.models.task import Task
from app.services.ai_service import get_ai_service
from app.services.cloudinary_service import upload_image
from app import db, limiter, socketio
from app.utils.input_validators import validate_message_content, sanitize_ai_input
from app.utils.security_decorators import require_tenant_access
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
    from app.models.user import User
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
    """Upload an image for chat messages"""
    try:
        # Validate file upload
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        file = request.files['image']

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
        allowed_extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

        # Determine MIME type
        mime_types = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        mime_type = mime_types.get(file_ext, 'image/png')

        # Upload to Cloudinary
        file.seek(0)
        upload_result = upload_image(file, folder="chat_images")

        return jsonify({
            'success': True,
            'url': upload_result['secure_url'],
            'filename': file.filename,
            'size': file_size,
            'type': mime_type
        })

    except Exception as e:
        current_app.logger.error(f"Error uploading chat image: {str(e)}")
        return jsonify({'error': 'Failed to upload image. Please try again.'}), 500


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
    if agent_id:
        agent = Agent.query.get(agent_id)
        if agent:
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
                        api_messages.append({
                            'role': 'user',
                            'content': msg.content
                        })
                    elif msg.agent_id == agent.id:  # Agent message
                        api_messages.append({
                            'role': 'assistant',
                            'content': msg.content
                        })

                # Add current message
                api_messages.append({
                    'role': 'user',
                    'content': content
                })

                # Fetch agent's assigned tasks (exclude completed)
                agent_tasks = Task.query.filter_by(
                    assigned_to_agent_id=agent.id,
                    tenant_id=g.current_tenant.id
                ).filter(Task.status != 'completed').all()

                # Build system prompt with tenant, user, and task context
                system_prompt = agent.build_system_prompt_with_context(
                    tenant=g.current_tenant,
                    user=current_user,
                    tasks=agent_tasks
                )

                # Get AI response (with MCP context if enabled)
                ai_service = get_ai_service()
                agent_response_text = ai_service.chat(
                    messages=api_messages,
                    system_prompt=system_prompt,
                    agent=agent,
                    user=current_user
                )

                # Save agent's response
                agent_message = Message(
                    content=agent_response_text,
                    agent_id=agent.id,
                    department_id=department_id
                )
                db.session.add(agent_message)
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
                    'mentioned_tasks': mentioned_tasks
                }

            except Exception as e:
                print(f"Error generating AI response: {e}")
                # Continue without agent response

    response_data = {
        'id': message.id,
        'content': message.content,
        'sender': message.get_sender_name(),
        'created_at': message.created_at.isoformat()
    }

    if agent_response:
        response_data['agent_response'] = agent_response

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

    # For now, allow all users to access public channels
    # TODO: Add membership checks for private channels
    if channel.is_private:
        # Check membership (to be implemented)
        pass

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

    data = request.get_json()
    content = data.get('content', '').strip()

    # Validate message content
    is_valid, error = validate_message_content(content)
    if not is_valid:
        return jsonify({'error': error}), 400

    # Sanitize AI input to prevent prompt injection
    is_safe, result = sanitize_ai_input(content)
    if not is_safe:
        return jsonify({'error': result}), 400

    # Create user's message
    message = Message(
        channel_id=channel.id,
        sender_id=current_user.id,
        content=content,
        message_type='text'
    )
    db.session.add(message)
    db.session.commit()

    # Broadcast user message via SSE
    conversation_id = f"channel_{slug}"
    socketio.emit('new_message', {
        'id': message.id,
        'content': message.content,
        'sender_id': current_user.id,
        'sender': current_user.full_name,
        'message_type': 'text',
        'created_at': message.created_at.isoformat()
    }, room=conversation_id)

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

    # 1. Always add explicitly mentioned agents
    for agent in mentioned_agents:
        if agent not in responding_agents:
            responding_agents.append(agent)

    # 2. Check for proactive participation (smart mode)
    # For agents associated with the channel (via department)
    for agent in associated_agents:
        if agent in mentioned_agents:
            continue  # Already added

        # Use Claude Haiku to detect if agent should proactively respond
        if should_agent_respond_proactively(agent, content, channel):
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

            # Build API messages
            api_messages = []
            for msg in channel_messages:
                if msg.sender_id:
                    api_messages.append({
                        'role': 'user',
                        'content': f"{msg.sender.full_name}: {msg.content}"
                    })
                elif msg.agent_id:
                    api_messages.append({
                        'role': 'assistant',
                        'content': msg.content
                    })

            # Build system prompt with channel context
            system_prompt = agent.build_system_prompt_with_context(
                tenant=g.current_tenant,
                user=current_user,
                tasks=[]
            )
            system_prompt += f"\n\nYou are participating in the #{channel.name} channel."
            if channel.description:
                system_prompt += f"\nChannel description: {channel.description}"

            # Get AI response (with MCP context if enabled)
            ai_service = get_ai_service()
            agent_response_text = ai_service.chat(
                messages=api_messages,
                system_prompt=system_prompt,
                agent=agent,
                user=current_user
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

            # Broadcast agent response via Socket.IO
            socketio.emit('new_message', {
                'id': agent_message.id,
                'content': agent_message.content,
                'agent_id': agent.id,
                'agent_name': agent.name,
                'message_type': 'text',
                'created_at': agent_message.created_at.isoformat(),
                'was_mentioned': agent in mentioned_agents
            }, room=conversation_id)

            agent_responses.append({
                'id': agent_message.id,
                'agent_id': agent.id,
                'agent_name': agent.name,
                'content': agent_message.content,
                'created_at': agent_message.created_at.isoformat(),
                'was_mentioned': agent in mentioned_agents
            })

        except Exception as e:
            print(f"Error generating agent response: {e}")
            continue

    return jsonify({
        'success': True,
        'message_id': message.id,
        'timestamp': message.created_at.isoformat(),
        'agent_responses': agent_responses
    })


def should_agent_respond_proactively(agent, message_content, channel):
    """
    Use Claude Haiku to determine if agent should proactively respond.
    Smart hybrid mode: responds to relevance, questions, and keywords.
    """
    try:
        ai_service = get_ai_service()

        detection_prompt = f"""Analyze this message in the #{channel.name} channel and determine if the {agent.name} agent should respond.

Agent role: {agent.description if hasattr(agent, 'description') and agent.description else agent.name}
Department: {agent.department.name if agent.department else 'None'}
Message: "{message_content}"

The agent should respond if:
1. The message asks a question related to their department or expertise
2. The message mentions topics relevant to their role
3. The message indicates urgency or need for assistance in their area
4. The message discusses tasks or issues they could help with

Return ONLY "yes" or "no"."""

        response = ai_service.chat(
            messages=[{'role': 'user', 'content': detection_prompt}],
            system_prompt="You are a relevance detection assistant. Respond only with 'yes' or 'no'.",
            model='claude-haiku-4-5-20251001',
            max_tokens=10,
            temperature=0
        ).strip().lower()

        return response == 'yes'

    except Exception as e:
        print(f"Error in proactive response detection: {e}")
        return False  # Default to not responding if detection fails


# === Channel Management ===

@chat_bp.route('/channel/<slug>/description', methods=['POST'])
@login_required
def update_channel_description(slug):
    """Update channel description"""
    channel = Channel.query.filter_by(slug=slug, tenant_id=g.current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

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
    channel = Channel.query.filter_by(slug=slug, tenant_id=current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

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
    if not user or user not in current_tenant.get_members():
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
    channel = Channel.query.filter_by(slug=slug, tenant_id=current_tenant.id).first()
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

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
    """Get unread message counts for all conversations"""
    unread_counts = {}

    # Get all channels
    channels = Channel.query.filter_by(tenant_id=g.current_tenant.id).all()
    for channel in channels:
        count = Message.count_unread_in_channel(channel.id, current_user.id)
        if count > 0:
            unread_counts[f'channel_{channel.slug}'] = count

    # Get all agents
    for department in g.current_tenant.get_departments():
        for agent in department.get_agents():
            count = Message.count_unread_from_agent(agent.id, current_user.id)
            if count > 0:
                unread_counts[f'agent_{agent.id}'] = count

    # Get all users (for DMs)
    for member in g.current_tenant.get_members():
        if member.id != current_user.id:
            count = Message.count_unread_from_user(member.id, current_user.id)
            if count > 0:
                unread_counts[f'user_{member.id}'] = count

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
