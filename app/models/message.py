from datetime import datetime
from app import db


class Message(db.Model):
    """Message model for chat conversations"""
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)

    # Message context - department channel, custom channel, or direct message
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=True, index=True)  # Custom channels
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # For DMs

    # Sender - either a user or an agent
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True, index=True)

    # Message content
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), default='text')  # text, image, system, notification

    # Attachments (for images and files)
    attachment_url = db.Column(db.String(500), nullable=True)  # Cloudinary URL
    attachment_type = db.Column(db.String(100), nullable=True)  # MIME type (image/png, image/jpeg, etc.)
    attachment_filename = db.Column(db.String(255), nullable=True)  # Original filename
    attachment_size = db.Column(db.Integer, nullable=True)  # File size in bytes

    # Metadata
    is_edited = db.Column(db.Boolean, default=False, nullable=False)
    edited_at = db.Column(db.DateTime)
    mentioned_agent_ids = db.Column(db.JSON, default=list)  # List of agent IDs mentioned in message

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='messages_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    agent = db.relationship('Agent', back_populates='messages')
    department = db.relationship('Department', back_populates='messages')
    channel = db.relationship('Channel', backref=db.backref('messages', lazy='dynamic'))

    def __repr__(self):
        return f'<Message id={self.id} from={self.get_sender_name()}>'

    def get_sender_name(self):
        """Get the name of the message sender"""
        if self.sender:
            return self.sender.full_name
        elif self.agent:
            return self.agent.name
        return 'System'

    def get_sender_avatar(self):
        """Get the avatar URL of the message sender"""
        if self.sender:
            return self.sender.avatar_url
        elif self.agent:
            return self.agent.avatar_url
        return None

    def is_from_agent(self):
        """Check if message is from an AI agent"""
        return self.agent_id is not None

    def is_from_user(self):
        """Check if message is from a user"""
        return self.sender_id is not None

    def is_direct_message(self):
        """Check if this is a direct message (not in a department channel)"""
        return self.recipient_id is not None and self.department_id is None

    def parse_mentions(self):
        """
        Parse @mentions from message content and return mentioned agents and users.
        Returns: {'agents': [agent_obj, ...], 'users': [user_obj, ...]}
        """
        import re
        from app.models.agent import Agent
        from app.models.user import User
        from app.models.channel import Channel

        # Find all @mentions in the content
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, self.content)

        result = {'agents': [], 'users': []}

        if not mentions:
            return result

        # Load channel if we have a channel_id but channel relationship not loaded
        channel = self.channel
        if not channel and self.channel_id:
            channel = Channel.query.get(self.channel_id)

        # Try to match mentions with agents and users
        if channel:
            try:
                # Get ALL agents in the tenant (not just channel-associated ones)
                # This allows @mentions to work in any channel regardless of setup
                from app.models.department import Department
                all_tenant_agents = Agent.query.join(Department).filter(
                    Department.tenant_id == channel.tenant_id
                ).all()

                print(f"[DEBUG] Channel {channel.id} tenant {channel.tenant_id}: Found {len(all_tenant_agents)} agents")
                print(f"[DEBUG] Mentions found: {mentions}")

                for mention_name in mentions:
                    # Try to find matching agent among all tenant agents
                    for agent in all_tenant_agents:
                        if mention_name.lower() in agent.name.lower():
                            print(f"[DEBUG] Matched @{mention_name} to agent {agent.name} (ID: {agent.id})")
                            if agent not in result['agents']:
                                result['agents'].append(agent)
                                break

                    # If not found in agents, try to find matching user
                    if mention_name.lower() not in [a.name.lower() for a in result['agents']]:
                        user = User.query.filter(
                            User.full_name.ilike(f'%{mention_name}%')
                        ).first()

                        if user and user not in result['users']:
                            result['users'].append(user)

                print(f"[DEBUG] parse_mentions result: {len(result['agents'])} agents, {len(result['users'])} users")
            except Exception as e:
                print(f"[ERROR] parse_mentions failed: {e}")
                import traceback
                traceback.print_exc()

        return result

    def parse_task_suggestions(self):
        """
        Parse task suggestions from agent message content.
        Returns: List of task dictionaries with suggested task data.
        Format:
            [TASK] Title: Task title here
            [TASK] Description: Task description (optional)
            [TASK] Priority: low|medium|high|urgent (optional)
            [TASK] Due: YYYY-MM-DD (optional)
            [TASK_END]
        """
        import re
        from datetime import datetime

        # Only parse task suggestions from agent messages
        if not self.is_from_agent():
            return []

        tasks = []

        # Find all task suggestion blocks
        task_pattern = r'\[TASK\](.*?)\[TASK_END\]'
        task_blocks = re.findall(task_pattern, self.content, re.DOTALL)

        for block in task_blocks:
            task_data = {
                'title': None,
                'description': None,
                'priority': 'medium',  # Default priority
                'due_date': None
            }

            # Parse individual fields within the task block
            # Claude may or may not include [TASK] prefix on each line
            lines = block.strip().split('\n')
            for line in lines:
                line = line.strip()

                # Parse title - with or without [TASK] prefix
                title_match = re.match(r'(?:\[TASK\]\s*)?Title:\s*(.+)', line)
                if title_match:
                    task_data['title'] = title_match.group(1).strip()[:200]  # Limit to 200 chars
                    continue

                # Parse description - with or without [TASK] prefix
                desc_match = re.match(r'(?:\[TASK\]\s*)?Description:\s*(.+)', line)
                if desc_match:
                    task_data['description'] = desc_match.group(1).strip()
                    continue

                # Parse priority - with or without [TASK] prefix
                priority_match = re.match(r'(?:\[TASK\]\s*)?Priority:\s*(low|medium|high|urgent)', line, re.IGNORECASE)
                if priority_match:
                    task_data['priority'] = priority_match.group(1).lower()
                    continue

                # Parse due date - with or without [TASK] prefix
                due_match = re.match(r'(?:\[TASK\]\s*)?Due:\s*(\d{4}-\d{2}-\d{2})', line)
                if due_match:
                    try:
                        task_data['due_date'] = datetime.strptime(due_match.group(1), '%Y-%m-%d')
                    except ValueError:
                        pass  # Invalid date, skip
                    continue

            # Only add task if it has a title
            if task_data['title']:
                tasks.append(task_data)

        return tasks

    def get_content_without_task_suggestions(self):
        """
        Get message content with task suggestion blocks removed.
        Useful for displaying clean message text to users.
        """
        import re

        # Remove task suggestion blocks
        clean_content = re.sub(r'\[TASK\].*?\[TASK_END\]', '', self.content, flags=re.DOTALL)

        # Clean up extra whitespace
        clean_content = re.sub(r'\n\n+', '\n\n', clean_content).strip()

        return clean_content

    @staticmethod
    def get_conversation(department_id=None, user1_id=None, user2_id=None, limit=50):
        """
        Get messages for a conversation
        Either department messages or direct messages between two users
        """
        query = Message.query

        if department_id:
            # Department channel messages
            query = query.filter_by(department_id=department_id)
        elif user1_id and user2_id:
            # Direct messages between two users
            query = query.filter(
                db.or_(
                    db.and_(Message.sender_id == user1_id, Message.recipient_id == user2_id),
                    db.and_(Message.sender_id == user2_id, Message.recipient_id == user1_id)
                )
            )

        return query.order_by(Message.created_at.asc()).limit(limit).all()

    @staticmethod
    def get_user_agent_conversation(user_id, agent_id, limit=50):
        """
        Get conversation history between a specific user and agent.
        This maintains separate conversation threads for each user.

        Args:
            user_id: The user's ID
            agent_id: The agent's ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages ordered by creation time (oldest first)
        """
        query = Message.query.filter(
            db.or_(
                # User messages to the agent
                db.and_(Message.sender_id == user_id, Message.agent_id == agent_id),
                # Agent messages (in the same department context)
                db.and_(Message.agent_id == agent_id, Message.sender_id == user_id)
            )
        )

        return query.order_by(Message.created_at.asc()).limit(limit).all()

    @staticmethod
    def count_unread_in_channel(channel_id, user_id):
        """
        Count unread messages in a channel for a specific user.

        Args:
            channel_id: The channel's ID
            user_id: The user's ID

        Returns:
            Number of unread messages
        """
        from app.models.read_receipt import ReadReceipt

        # Get all messages in the channel
        message_ids = db.session.query(Message.id).filter(
            Message.channel_id == channel_id,
            Message.sender_id != user_id  # Don't count own messages
        ).subquery()

        # Count messages that don't have a read receipt for this user
        unread_count = db.session.query(db.func.count(message_ids.c.id)).filter(
            ~db.exists().where(
                db.and_(
                    ReadReceipt.message_id == message_ids.c.id,
                    ReadReceipt.user_id == user_id
                )
            )
        ).scalar()

        return unread_count or 0

    @staticmethod
    def count_unread_from_agent(agent_id, user_id):
        """
        Count unread messages from an agent to a specific user.

        Args:
            agent_id: The agent's ID
            user_id: The user's ID

        Returns:
            Number of unread messages
        """
        from app.models.read_receipt import ReadReceipt

        # Get agent messages to this user
        message_ids = db.session.query(Message.id).filter(
            Message.agent_id == agent_id,
            Message.sender_id == user_id  # Messages in conversation with this user
        ).subquery()

        # Count messages without read receipts
        unread_count = db.session.query(db.func.count(message_ids.c.id)).filter(
            ~db.exists().where(
                db.and_(
                    ReadReceipt.message_id == message_ids.c.id,
                    ReadReceipt.user_id == user_id
                )
            )
        ).scalar()

        return unread_count or 0

    @staticmethod
    def count_unread_from_user(other_user_id, current_user_id):
        """
        Count unread messages from another user to current user.

        Args:
            other_user_id: The other user's ID
            current_user_id: The current user's ID

        Returns:
            Number of unread messages
        """
        from app.models.read_receipt import ReadReceipt

        # Get messages from other user to current user
        message_ids = db.session.query(Message.id).filter(
            Message.sender_id == other_user_id,
            Message.recipient_id == current_user_id
        ).subquery()

        # Count messages without read receipts
        unread_count = db.session.query(db.func.count(message_ids.c.id)).filter(
            ~db.exists().where(
                db.and_(
                    ReadReceipt.message_id == message_ids.c.id,
                    ReadReceipt.user_id == current_user_id
                )
            )
        ).scalar()

        return unread_count or 0

    def mark_as_read(self, user_id):
        """
        Mark this message as read by a user.

        Args:
            user_id: ID of the user who read the message

        Returns:
            ReadReceipt instance
        """
        from app.models.read_receipt import ReadReceipt

        # Check if already marked as read
        existing_receipt = ReadReceipt.query.filter_by(
            message_id=self.id,
            user_id=user_id
        ).first()

        if existing_receipt:
            return existing_receipt

        # Create new read receipt
        receipt = ReadReceipt(
            message_id=self.id,
            user_id=user_id
        )
        db.session.add(receipt)
        db.session.commit()

        return receipt

    def is_read_by(self, user_id):
        """
        Check if message has been read by a user.

        Args:
            user_id: ID of the user to check

        Returns:
            True if read, False otherwise
        """
        from app.models.read_receipt import ReadReceipt

        return ReadReceipt.query.filter_by(
            message_id=self.id,
            user_id=user_id
        ).first() is not None

    def get_read_by_users(self):
        """
        Get list of users who have read this message.

        Returns:
            List of User objects
        """
        from app.models.read_receipt import ReadReceipt
        from app.models.user import User

        return User.query.join(ReadReceipt).filter(
            ReadReceipt.message_id == self.id
        ).all()
