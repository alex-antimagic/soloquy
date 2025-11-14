from datetime import datetime
import json
from app import db


class Agent(db.Model):
    """AI Agent model for department-specific assistants"""
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False, index=True)

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

    # Integration access control
    enable_quickbooks = db.Column(db.Boolean, default=True, nullable=False)  # Allow access to QuickBooks data

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    department = db.relationship('Department', back_populates='agents')
    messages = db.relationship('Message', back_populates='agent', lazy='dynamic')

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
            context_parts.append(f"You are currently assisting {user.full_name}.")

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
