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

    # Integration access control (secure by default - admin must explicitly enable)
    enable_quickbooks = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to QuickBooks data
    enable_gmail = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to Gmail (MCP)
    enable_outlook = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to Outlook (MCP)
    enable_google_drive = db.Column(db.Boolean, default=False, nullable=False)  # Allow access to Google Drive (MCP)
    enable_website_builder = db.Column(db.Boolean, default=False, nullable=False)  # Allow AI to create/edit website content

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

        # Get messages in this agent's department where:
        # - User sent the message, OR
        # - This agent sent the message
        query = Message.query.filter(
            Message.department_id == self.department_id,
            db.or_(
                Message.sender_id == user_id,  # User's messages
                Message.agent_id == self.id     # This agent's responses
            )
        )

        return query.order_by(Message.created_at.asc()).limit(limit).all()

    def build_system_prompt_with_context(self, tenant=None, user=None, tasks=None):
        """
        Build the complete system prompt including tenant and user context.

        This gives the agent awareness of:
        - Which workspace/tenant they're operating in
        - Who they're talking to
        - Their department and role
        - Their assigned tasks

        Args:
            tenant: The Tenant object for workspace context
            user: The User object for personalization
            tasks: List of Task objects assigned to this agent

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
