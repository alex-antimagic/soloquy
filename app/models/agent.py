from datetime import datetime
import json
from app import db


class Agent(db.Model):
    """AI Agent model for department-specific assistants"""
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Agent identity
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))

    # Agent configuration
    system_prompt = db.Column(db.Text)  # Custom instructions for Claude
    model = db.Column(db.String(50), default='claude-haiku-4-5-20251001')  # Claude model to use
    temperature = db.Column(db.Float, default=1.0)  # Response creativity (0-1)
    max_tokens = db.Column(db.Integer, default=4096)  # Max response length

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)  # Primary agent for department

    # Agent type: 'specialist' or 'orchestrator'
    agent_type = db.Column(db.String(20), nullable=False, default='specialist')

    # Integration access control (secure by default - admin must explicitly enable)
    enable_quickbooks = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to QuickBooks data
    enable_gmail = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to Gmail (MCP)
    enable_outlook = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to Outlook (MCP)
    enable_google_drive = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to Google Drive (MCP)
    enable_website_builder = db.Column(db.Boolean, default=False, nullable=False)  # Allow AI to create/edit website content
    enable_file_generation = db.Column(db.Boolean, default=True, nullable=False)  # Allow AI to generate files (PDF, CSV, Excel)
    enable_competitive_analysis = db.Column(db.Boolean, default=False, nullable=False)  # Allow AI to perform competitive analysis
    enable_hr_management = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to HR data and operations
    enable_similar_lead_discovery = db.Column(db.Boolean, default=False, nullable=False)  # Allow AI to discover similar leads
    enable_cross_applet_data_access = db.Column(db.Boolean, default=True, nullable=False)  # Allow read-only queries across all applets (CRM, HR, Support, Projects)

    # User access control (who can chat with this agent)
    access_control = db.Column(db.String(20), default='all', nullable=False)  # 'all', 'role', 'department', 'users'
    allowed_roles = db.Column(db.Text)  # JSON array: ['owner', 'admin'] when access_control='role'
    allowed_department_ids = db.Column(db.Text)  # JSON array: [1, 2, 3] when access_control='department'
    allowed_user_ids = db.Column(db.Text)  # JSON array: [5, 10, 15] when access_control='users'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    department = db.relationship('Department', back_populates='agents')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    messages = db.relationship('Message', back_populates='agent', lazy='dynamic')
    versions = db.relationship('AgentVersion', back_populates='agent',
                               order_by='AgentVersion.version_number.desc()',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Agent {self.name}>'

    def can_user_access(self, user):
        """
        Check if a user has access to chat with this agent.

        Args:
            user: User object to check access for

        Returns:
            Boolean indicating whether user has access
        """
        # All users have access by default
        if self.access_control == 'all':
            return True

        # Role-based access
        if self.access_control == 'role':
            if not self.allowed_roles:
                return False
            try:
                allowed_role_list = json.loads(self.allowed_roles)
                user_role = user.get_role_in_tenant(self.department.tenant_id)
                return user_role in allowed_role_list
            except (json.JSONDecodeError, AttributeError):
                return False

        # Department-based access
        if self.access_control == 'department':
            if not self.allowed_department_ids:
                return False
            try:
                allowed_dept_list = json.loads(self.allowed_department_ids)

                # Check if user has access to ANY of the allowed departments
                from app.models.department import Department
                for dept_id in allowed_dept_list:
                    department = Department.query.get(dept_id)
                    if department and department.can_user_access(user):
                        return True

                return False
            except (json.JSONDecodeError, AttributeError):
                return False

        # User-specific access
        if self.access_control == 'users':
            if not self.allowed_user_ids:
                return False
            try:
                allowed_user_list = json.loads(self.allowed_user_ids)
                return user.id in allowed_user_list
            except (json.JSONDecodeError, AttributeError):
                return False

        # Default to no access if access_control is unrecognized
        return False

    def get_accessible_users(self):
        """
        Get list of users who have access to this agent.

        Returns:
            List of User objects who can access this agent
        """
        from app.models.user import User

        # All workspace users have access
        if self.access_control == 'all':
            return self.department.tenant.get_members()

        accessible_users = []

        # Role-based access
        if self.access_control == 'role':
            if self.allowed_roles:
                try:
                    allowed_role_list = json.loads(self.allowed_roles)
                    all_members = self.department.tenant.get_members()
                    for user in all_members:
                        user_role = user.get_role_in_tenant(self.department.tenant_id)
                        if user_role in allowed_role_list:
                            accessible_users.append(user)
                except (json.JSONDecodeError, AttributeError):
                    pass

        # Department-based access (simplified: all workspace users for now)
        elif self.access_control == 'department':
            # In a full implementation, this would check which users belong to allowed departments
            # For now, return all workspace users
            accessible_users = self.department.tenant.get_members()

        # User-specific access
        elif self.access_control == 'users':
            if self.allowed_user_ids:
                try:
                    allowed_user_list = json.loads(self.allowed_user_ids)
                    accessible_users = User.query.filter(User.id.in_(allowed_user_list)).all()
                except (json.JSONDecodeError, AttributeError):
                    pass

        return accessible_users

    def get_conversation_history(self, limit=20):
        """Get recent conversation history for context"""
        return self.messages.order_by(Message.created_at.desc()).limit(limit).all()

    def get_conversation_with_user(self, user_id, limit=20):
        """
        Get conversation history between this agent and a specific user.
        Maintains separate conversation threads per user.

        Args:
            user_id: The user's ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages ordered by creation time (oldest first)
        """
        from app.models.message import Message

        # Get messages where:
        # - This specific agent is involved (agent_id is set)
        # - Message is either FROM the user (sender_id = user_id) OR
        # - Message is FROM the agent (sender_id is None)
        query = Message.query.filter(
            Message.agent_id == self.id,  # Only this agent's messages
            db.or_(
                Message.sender_id == user_id,  # User's messages to this agent
                Message.sender_id.is_(None)     # This agent's responses (sender_id is None for agent messages)
            )
        )

        return query.order_by(Message.created_at.asc()).limit(limit).all()

    def get_last_message_time(self):
        """Get timestamp of the last message from this agent"""
        from app.models.message import Message
        last_message = Message.query.filter_by(
            agent_id=self.id
        ).order_by(Message.created_at.desc()).first()
        return last_message.created_at if last_message else None

    def build_system_prompt_with_context(self, tenant=None, user=None, tasks=None, generated_files=None):
        """
        Build the complete system prompt including tenant and user context.

        This gives the agent awareness of:
        - Which workspace/tenant they're operating in
        - Who they're talking to
        - Their department and role
        - Their assigned tasks
        - Recently generated files

        Args:
            tenant: The Tenant object for workspace context
            user: The User object for personalization
            tasks: List of Task objects assigned to this agent
            generated_files: List of recently generated files

        Returns:
            Complete system prompt string
        """
        context_parts = []

        # Chat format instructions (FIRST - most important)
        context_parts.append("=== IMPORTANT: CONVERSATION FORMAT ===")
        context_parts.append("This is a real-time chat conversation, not a document or report.")
        context_parts.append("Respond naturally and conversationally, as you would in a messaging app.")
        context_parts.append("- Keep responses concise and friendly")
        context_parts.append("- Don't use markdown headings (# ##) or excessive formatting")
        context_parts.append("- Only use bullet points or lists when genuinely helpful for clarity")
        context_parts.append("- Respond like you're chatting with a colleague, not writing an email or document")
        context_parts.append("")

        # Business Intelligence Context (HIGH PRIORITY)
        if tenant and tenant.business_context:
            try:
                business_data = json.loads(tenant.business_context)

                context_parts.append("=== BUSINESS CONTEXT ===")

                if business_data.get('company_description'):
                    context_parts.append(f"Company Overview: {business_data['company_description']}")

                if business_data.get('industry'):
                    context_parts.append(f"Industry: {business_data['industry']}")

                if business_data.get('products_services'):
                    products = ', '.join(business_data['products_services'][:5])  # Limit to 5
                    context_parts.append(f"Products/Services: {products}")

                if business_data.get('target_market'):
                    context_parts.append(f"Target Market: {business_data['target_market']}")

                if business_data.get('value_proposition'):
                    context_parts.append(f"Value Proposition: {business_data['value_proposition']}")

                if tenant.company_size:
                    context_parts.append(f"Company Size: {tenant.company_size} employees")

                context_parts.append("")  # Blank line for separation

            except json.JSONDecodeError:
                pass  # Skip if business context is malformed

        # QuickBooks Financial Data (HIGH PRIORITY)
        if tenant:
            from app.models.integration import Integration
            from app.services.quickbooks_service import quickbooks_service

            qb_integration = Integration.query.filter_by(
                tenant_id=tenant.id,
                integration_type='quickbooks',
                is_active=True
            ).first()

            # Only add QuickBooks data if agent has access enabled
            if qb_integration and self.enable_quickbooks:
                try:
                    financial_data = quickbooks_service.get_financial_summary(qb_integration)

                    if financial_data:
                        context_parts.append("=== QUICKBOOKS FINANCIAL DATA ===")

                        if financial_data.get('company'):
                            company = financial_data['company']
                            context_parts.append(f"Company: {company.get('company_name', 'N/A')}")

                        if financial_data.get('metrics'):
                            metrics = financial_data['metrics']
                            context_parts.append(f"Accounts Receivable: ${metrics.get('total_accounts_receivable', 0):,.2f}")
                            context_parts.append(f"Open Invoices: {metrics.get('num_open_invoices', 0)} totaling ${metrics.get('total_open_invoices', 0):,.2f}")
                            if metrics.get('num_overdue_invoices', 0) > 0:
                                context_parts.append(f"⚠️ Overdue Invoices: {metrics['num_overdue_invoices']} totaling ${metrics.get('total_overdue', 0):,.2f}")

                        if financial_data.get('profit_loss'):
                            pl = financial_data['profit_loss']
                            context_parts.append(f"\nProfit & Loss ({pl.get('start_date')} to {pl.get('end_date')}):")
                            context_parts.append(f"  Revenue: ${pl.get('total_revenue', 0):,.2f}")
                            context_parts.append(f"  Expenses: ${pl.get('total_expenses', 0):,.2f}")
                            context_parts.append(f"  Net Income: ${pl.get('net_income', 0):,.2f}")

                        if financial_data.get('top_customers'):
                            context_parts.append("\nTop Customers by Balance:")
                            for customer in financial_data['top_customers'][:3]:
                                context_parts.append(f"  - {customer['name']}: ${customer['balance']:,.2f}")

                        if financial_data.get('overdue_invoices'):
                            overdue = financial_data['overdue_invoices'][:3]
                            if overdue:
                                context_parts.append("\n⚠️ Overdue Invoices (Action Required):")
                                for inv in overdue:
                                    context_parts.append(f"  - Invoice #{inv.get('invoice_number')}: {inv.get('customer_name')} - ${inv.get('balance'):,.2f} (Due: {inv.get('due_date')})")

                        context_parts.append("")  # Blank line for separation

                except Exception as e:
                    # Silently skip if QuickBooks data fetch fails
                    print(f"Error fetching QuickBooks data for agent context: {e}")
                    pass

        # Custom User-Provided Context (HIGH PRIORITY)
        if tenant and tenant.custom_context:
            context_parts.append("=== CUSTOM WORKSPACE CONTEXT ===")
            context_parts.append(tenant.custom_context)
            context_parts.append("")  # Blank line for separation

        # Timezone Context (for calendar/scheduling operations)
        if user and hasattr(user, 'timezone_preference') and user.timezone_preference:
            from datetime import datetime
            import pytz

            context_parts.append("=== TIMEZONE CONTEXT ===")
            context_parts.append(f"User's timezone: {user.timezone_preference}")

            # Show current time in user's timezone
            try:
                user_tz = pytz.timezone(user.timezone_preference)
                current_time = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(user_tz)
                context_parts.append(f"Current time in user's timezone: {current_time.strftime('%Y-%m-%d %I:%M %p %Z')}")
            except:
                pass

            context_parts.append("IMPORTANT: When creating calendar events or displaying times, always:")
            context_parts.append(f"1. Show times in {user.timezone_preference} format (include timezone abbreviation like 'PST', 'EST', etc.)")
            context_parts.append("2. Convert user's local time inputs to UTC for API calls")
            context_parts.append("3. Display 'Creating calendar event at 2pm PST' to confirm timezone")
            context_parts.append("")

        # Workspace context
        if tenant:
            context_parts.append(f"You are working in the '{tenant.name}' workspace.")
            if tenant.description:
                context_parts.append(f"Workspace description: {tenant.description}")

        # User context
        if user:
            user_intro = f"You are currently assisting {user.full_name}"
            if user.title:
                user_intro += f" ({user.title})"
            user_intro += "."
            context_parts.append(user_intro)

        # Department context
        context_parts.append(f"You are {self.name}, the AI assistant for the {self.department.name} department.")
        if self.description:
            context_parts.append(f"Your role: {self.description}")

        # Task context
        if tasks:
            context_parts.append("\n=== YOUR ASSIGNED TASKS ===")
            context_parts.append("You have the following tasks assigned to you:")

            for task in tasks:
                task_info = [f"- [{task.status.upper()}] {task.title}"]

                if task.description:
                    task_info.append(f"  Description: {task.description}")

                if task.due_date:
                    task_info.append(f"  Due: {task.due_date.strftime('%Y-%m-%d')}")
                    if task.is_overdue():
                        task_info.append("  ⚠️ OVERDUE - Address this proactively!")

                if task.priority:
                    task_info.append(f"  Priority: {task.priority}")

                context_parts.extend(task_info)

            context_parts.append("\nTask Handling Instructions:")
            context_parts.append("- If you have an 'introduce yourself' task that is pending or overdue, complete it naturally during the conversation by introducing yourself.")
            context_parts.append("- For simple tasks that you can complete during conversation (like introductions), do so naturally and mention completing the task.")
            context_parts.append("- For complex tasks requiring human input or decisions, proactively ask the user about them during relevant conversation moments.")
            context_parts.append("- Always be helpful and proactive about your assigned tasks without being pushy.")
            context_parts.append("")


        # Recently Generated Files Context
        if generated_files and len(generated_files) > 0:
            context_parts.append("\n=== RECENTLY GENERATED FILES ===")
            context_parts.append("You have recently generated the following files in this conversation:")
            for file in generated_files:
                context_parts.append(f"- {file.filename} ({file.file_type.upper()}, {file.file_size_display})")
                context_parts.append(f"  URL: {file.cloudinary_url}")
                if file.file_purpose:
                    context_parts.append(f"  Purpose: {file.file_purpose}")
            context_parts.append("\nYou can reference these files, use their data, or build upon them.")
            context_parts.append("If asked to work with a file you just created, use the URL above to access it.")
            context_parts.append("")

        # Add custom system prompt
        if self.system_prompt:
            context_parts.append("\n" + self.system_prompt)

        return "\n".join(context_parts)

    # Version management methods
    def create_version(self, changed_by_user, change_summary=None, change_type='update'):
        """
        Create a new version snapshot of this agent

        Args:
            changed_by_user: User making the change
            change_summary: Optional manual description (auto-generated if None)
            change_type: Type of change (initial, update, rollback, import)

        Returns:
            New AgentVersion instance (committed to database)
        """
        from app.models.agent_version import AgentVersion

        # Get previous active version for diff
        previous_version = self.get_active_version()

        # Create new version
        new_version = AgentVersion.create_from_agent(
            agent=self,
            changed_by_user=changed_by_user,
            change_summary=change_summary,
            change_type=change_type,
            previous_version=previous_version
        )

        # Deactivate previous version
        if previous_version:
            previous_version.is_active_version = False

        # Activate new version
        new_version.is_active_version = True

        db.session.add(new_version)
        db.session.commit()

        return new_version

    def get_active_version(self):
        """Get the currently active/published version"""
        from app.models.agent_version import AgentVersion
        return AgentVersion.query.filter_by(
            agent_id=self.id,
            is_active_version=True
        ).first()

    def get_latest_version(self):
        """Get the most recent version (may not be active)"""
        from app.models.agent_version import AgentVersion
        return AgentVersion.query.filter_by(agent_id=self.id)\
            .order_by(AgentVersion.version_number.desc()).first()

    def get_version_history(self, limit=None):
        """
        Get all versions in reverse chronological order

        Args:
            limit: Optional limit on number of versions to return

        Returns:
            List of AgentVersion instances
        """
        from app.models.agent_version import AgentVersion
        query = AgentVersion.query.filter_by(agent_id=self.id)\
            .order_by(AgentVersion.version_number.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_next_version_number(self):
        """Get the next version number for this agent"""
        from app.models.agent_version import AgentVersion
        max_version = db.session.query(db.func.max(AgentVersion.version_number))\
            .filter_by(agent_id=self.id).scalar()
        return (max_version or 0) + 1

    def rollback_to_version(self, version_id, current_user, reason=None):
        """
        Rollback to a previous version (creates a new version, doesn't delete history)

        Args:
            version_id: ID of version to restore
            current_user: User performing the rollback
            reason: Optional reason for rollback

        Returns:
            New AgentVersion instance
        """
        from app.models.agent_version import AgentVersion

        # Get target version
        target_version = AgentVersion.query.get(version_id)
        if not target_version or target_version.agent_id != self.id:
            raise ValueError("Invalid version ID")

        # Copy all fields from target version to current agent
        self.name = target_version.name
        self.description = target_version.description
        self.avatar_url = target_version.avatar_url
        self.system_prompt = target_version.system_prompt
        self.model = target_version.model
        self.temperature = target_version.temperature
        self.max_tokens = target_version.max_tokens
        self.enable_quickbooks = target_version.enable_quickbooks
        self.enable_gmail = target_version.enable_gmail
        self.enable_outlook = target_version.enable_outlook
        self.enable_google_drive = target_version.enable_google_drive
        self.enable_website_builder = target_version.enable_website_builder
        self.enable_file_generation = target_version.enable_file_generation
        self.enable_competitive_analysis = target_version.enable_competitive_analysis
        self.enable_hr_management = target_version.enable_hr_management
        self.enable_cross_applet_data_access = getattr(target_version, 'enable_cross_applet_data_access', True)  # Default True if version doesn't have field
        self.access_control = target_version.access_control
        self.allowed_roles = target_version.allowed_roles
        self.allowed_department_ids = target_version.allowed_department_ids
        self.allowed_user_ids = target_version.allowed_user_ids

        # Generate rollback summary
        rollback_summary = f"Rolled back to version {target_version.version_number}"
        if reason:
            rollback_summary += f": {reason}"

        # Create new version (rollback is just a new version)
        new_version = self.create_version(
            changed_by_user=current_user,
            change_summary=rollback_summary,
            change_type='rollback'
        )

        return new_version

    def compare_versions(self, version1_id, version2_id):
        """
        Compare two versions and return the differences

        Args:
            version1_id: ID of first version
            version2_id: ID of second version

        Returns:
            Dictionary with diff information
        """
        from app.models.agent_version import AgentVersion

        v1 = AgentVersion.query.get(version1_id)
        v2 = AgentVersion.query.get(version2_id)

        if not v1 or not v2 or v1.agent_id != self.id or v2.agent_id != self.id:
            raise ValueError("Invalid version IDs")

        # Use v2's diff if it exists and was compared against v1
        if v2.get_changes():
            return {
                'version1': v1.to_dict(),
                'version2': v2.to_dict(include_diff=True),
                'changes': v2.get_changes()
            }

        # Otherwise generate diff on the fly
        diff = AgentVersion._generate_diff(v1, v2)
        return {
            'version1': v1.to_dict(),
            'version2': v2.to_dict(),
            'changes': diff
        }

    def export_to_json(self):
        """
        Export agent configuration as JSON for sharing/backup

        Returns:
            Dictionary containing complete agent configuration
        """
        return {
            'export_version': '1.0',
            'export_date': datetime.utcnow().isoformat(),
            'agent': {
                'name': self.name,
                'description': self.description,
                'avatar_url': self.avatar_url,
                'system_prompt': self.system_prompt,
                'model': self.model,
                'temperature': self.temperature,
                'max_tokens': self.max_tokens,
                'is_active': self.is_active,
                'enable_quickbooks': self.enable_quickbooks,
                'enable_gmail': self.enable_gmail,
                'enable_outlook': self.enable_outlook,
                'enable_google_drive': self.enable_google_drive,
                'enable_website_builder': self.enable_website_builder,
                'enable_file_generation': self.enable_file_generation,
                'enable_competitive_analysis': self.enable_competitive_analysis,
                'enable_hr_management': self.enable_hr_management,
                'enable_similar_lead_discovery': self.enable_similar_lead_discovery,
                'enable_cross_applet_data_access': self.enable_cross_applet_data_access,
                'access_control': self.access_control,
                'allowed_roles': self.allowed_roles,
                'allowed_department_ids': self.allowed_department_ids,
                'allowed_user_ids': self.allowed_user_ids
            },
            'metadata': {
                'original_agent_id': self.id,
                'original_department': self.department.name,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'created_by': self.created_by.full_name if self.created_by else None
            }
        }

    @staticmethod
    def import_from_json(json_data, department_id, created_by_user, import_mode='new'):
        """
        Import agent configuration from JSON

        Args:
            json_data: Dictionary with agent configuration
            department_id: Department to create agent in
            created_by_user: User performing the import
            import_mode: 'new' to create new agent, 'version' to add as version to existing

        Returns:
            Tuple of (Agent instance, version_number, was_created)

        Raises:
            ValueError: If JSON is invalid or missing required fields
        """
        # Validate JSON structure
        if 'agent' not in json_data:
            raise ValueError("Invalid agent export: missing 'agent' section")

        agent_data = json_data['agent']

        # Validate required fields
        required_fields = ['name', 'system_prompt']
        missing_fields = [f for f in required_fields if f not in agent_data or not agent_data[f]]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Security: Sanitize system prompt to prevent injection attacks
        system_prompt = agent_data['system_prompt']

        # Check for dangerous patterns
        dangerous_patterns = [
            'ignore previous instructions',
            'disregard above',
            'system:',
            'admin:',
            '<script',
            'javascript:',
            'exec(',
            'eval(',
            '__import__'
        ]

        system_prompt_lower = system_prompt.lower()
        for pattern in dangerous_patterns:
            if pattern in system_prompt_lower:
                raise ValueError(f"System prompt contains potentially dangerous content: '{pattern}'")

        # Limit length to prevent resource exhaustion
        if len(system_prompt) > 10000:
            raise ValueError("System prompt exceeds maximum length of 10,000 characters")

        # Validate name length and characters
        name = agent_data['name']
        if len(name) > 255:
            raise ValueError("Agent name exceeds maximum length of 255 characters")
        if len(name) < 1:
            raise ValueError("Agent name cannot be empty")

        # Validate model choice
        valid_models = [
            'claude-haiku-4-5-20251001',
            'claude-sonnet-4-5-20250929',
            'claude-opus-4-20250514'
        ]
        model = agent_data.get('model', 'claude-haiku-4-5-20251001')
        if model not in valid_models:
            raise ValueError(f"Invalid model: {model}. Must be one of: {', '.join(valid_models)}")

        # Validate temperature
        temperature = agent_data.get('temperature', 1.0)
        if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        # Validate max_tokens
        max_tokens = agent_data.get('max_tokens', 4096)
        if not isinstance(max_tokens, int) or not 256 <= max_tokens <= 8192:
            raise ValueError("Max tokens must be between 256 and 8192")

        # Create new agent
        new_agent = Agent(
            department_id=department_id,
            created_by_id=created_by_user.id,
            name=agent_data['name'],
            description=agent_data.get('description'),
            avatar_url=agent_data.get('avatar_url'),
            system_prompt=agent_data['system_prompt'],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            is_active=agent_data.get('is_active', True),
            enable_quickbooks=agent_data.get('enable_quickbooks', False),
            enable_gmail=agent_data.get('enable_gmail', False),
            enable_outlook=agent_data.get('enable_outlook', False),
            enable_google_drive=agent_data.get('enable_google_drive', False),
            enable_website_builder=agent_data.get('enable_website_builder', False),
            enable_file_generation=agent_data.get('enable_file_generation', False),
            enable_competitive_analysis=agent_data.get('enable_competitive_analysis', False),
            enable_hr_management=agent_data.get('enable_hr_management', False),
            enable_similar_lead_discovery=agent_data.get('enable_similar_lead_discovery', False),
            enable_cross_applet_data_access=agent_data.get('enable_cross_applet_data_access', True),
            access_control=agent_data.get('access_control', 'all'),
            allowed_roles=agent_data.get('allowed_roles'),
            allowed_department_ids=agent_data.get('allowed_department_ids'),
            allowed_user_ids=agent_data.get('allowed_user_ids'),
            is_primary=False  # Imported agents are never primary
        )

        db.session.add(new_agent)
        db.session.flush()  # Get ID

        # Create initial version
        change_summary = f"Imported from {json_data.get('metadata', {}).get('original_department', 'external source')}"
        new_agent.create_version(
            changed_by_user=created_by_user,
            change_summary=change_summary,
            change_type='import'
        )

        db.session.commit()

        return new_agent, 1, True

    def is_orchestrator(self):
        """Check if this agent is an orchestrator type"""
        return self.agent_type == 'orchestrator'

    def is_visible_to_user(self, user):
        """
        Check if this agent should be visible in the sidebar for a given user.

        Args:
            user: User object to check visibility for

        Returns:
            Boolean indicating whether the agent should be visible
        """
        # First check if user has access at all
        if not self.can_user_access(user):
            return False

        # Show all accessible agents in sidebar
        return True

    def get_user_preferred_mode(self, user):
        """
        Get user's preferred interaction mode (orchestrator vs direct).

        Args:
            user: User object

        Returns:
            String: 'orchestrator' or 'direct' (defaults to 'direct')
        """
        # Default to direct mode (show all agents)
        return 'direct'
