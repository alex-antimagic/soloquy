"""
AI Service for Claude API Integration
Uses Claude Haiku for fast, cost-effective agent responses
Supports Model Context Protocol (MCP) for external data access
"""
import os
import json
from anthropic import Anthropic
from typing import List, Dict, Optional, Any
from flask import current_app


class AIService:
    """Service for interacting with Claude AI"""

    # Use Claude Haiku 4.5 for fast, efficient responses
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.client = Anthropic(api_key=api_key)

    def _build_mcp_config(self, agent, user) -> Optional[List[Dict[str, Any]]]:
        """
        Build MCP server configuration from agent's enabled integrations

        SECURITY: Personal integrations are ONLY accessible if:
        - The agent was created by the current user, OR
        - The integration belongs to the current user

        Workspace integrations are always accessible (admin-controlled).

        Args:
            agent: Agent model with integration flags (enable_gmail, etc.)
            user: User model for checking personal integrations

        Returns:
            List of MCP server configurations for Anthropic API, or None if no MCP integrations
        """
        from app.models.integration import Integration
        from app.models.audit_log import AuditLog
        from app.services.mcp_manager import mcp_manager
        from flask import request, g

        mcp_servers = []

        # Determine if current user can access personal integrations from this agent
        # Rule: Agent must be created by current user to access their personal integrations
        can_access_personal = (agent.created_by_id == user.id)

        # Gmail MCP
        if agent.enable_gmail:
            gmail_integration = None

            # Check workspace Gmail first (always accessible)
            gmail_workspace = Integration.query.filter_by(
                tenant_id=agent.department.tenant_id,
                integration_type='gmail',
                owner_type='tenant',
                owner_id=agent.department.tenant_id,
                is_active=True
            ).first()

            if gmail_workspace:
                gmail_integration = gmail_workspace
            elif can_access_personal:
                # Only check personal if user created this agent
                gmail_personal = Integration.query.filter_by(
                    tenant_id=agent.department.tenant_id,
                    integration_type='gmail',
                    owner_type='user',
                    owner_id=user.id,
                    is_active=True
                ).first()
                gmail_integration = gmail_personal
            else:
                # Log denied access attempt
                current_app.logger.warning(
                    f"MCP_ACCESS_DENIED: user={user.id} agent={agent.id} "
                    f"integration_type=gmail reason=agent_not_created_by_user"
                )
                AuditLog.log_access_denied(
                    user_id=user.id,
                    tenant_id=g.current_tenant.id if hasattr(g, 'current_tenant') else agent.department.tenant_id,
                    resource_type='integration',
                    resource_id=None,
                    reason='Personal Gmail access denied - agent not created by user',
                    agent_id=agent.id,
                    ip_address=request.remote_addr if request else None
                )

            if gmail_integration:
                status = mcp_manager.get_process_status(gmail_integration)
                if status.get('running'):
                    # Log successful MCP access
                    AuditLog.log_mcp_access(
                        user_id=user.id,
                        tenant_id=g.current_tenant.id if hasattr(g, 'current_tenant') else agent.department.tenant_id,
                        agent_id=agent.id,
                        integration=gmail_integration,
                        status='success',
                        ip_address=request.remote_addr if request else None
                    )

                    mcp_servers.append({
                        'name': f'gmail_{gmail_integration.owner_type}',
                        'integration_id': gmail_integration.id,
                        'mcp_process_name': gmail_integration.get_mcp_process_name(),
                        'tools': ['gmail_list', 'gmail_read', 'gmail_send', 'gmail_search', 'gmail_labels']
                    })

        # Outlook MCP
        if agent.enable_outlook:
            outlook_integration = None

            # Check workspace Outlook first (always accessible)
            outlook_workspace = Integration.query.filter_by(
                tenant_id=agent.department.tenant_id,
                integration_type='outlook',
                owner_type='tenant',
                owner_id=agent.department.tenant_id,
                is_active=True
            ).first()

            if outlook_workspace:
                outlook_integration = outlook_workspace
            elif can_access_personal:
                # Only check personal if user created this agent
                outlook_personal = Integration.query.filter_by(
                    tenant_id=agent.department.tenant_id,
                    integration_type='outlook',
                    owner_type='user',
                    owner_id=user.id,
                    is_active=True
                ).first()
                outlook_integration = outlook_personal
            else:
                # Log denied access attempt
                current_app.logger.warning(
                    f"MCP_ACCESS_DENIED: user={user.id} agent={agent.id} "
                    f"integration_type=outlook reason=agent_not_created_by_user"
                )
                AuditLog.log_access_denied(
                    user_id=user.id,
                    tenant_id=g.current_tenant.id if hasattr(g, 'current_tenant') else agent.department.tenant_id,
                    resource_type='integration',
                    resource_id=None,
                    reason='Personal Outlook access denied - agent not created by user',
                    agent_id=agent.id,
                    ip_address=request.remote_addr if request else None
                )

            if outlook_integration:
                status = mcp_manager.get_process_status(outlook_integration)
                if status.get('running'):
                    # Log successful MCP access
                    AuditLog.log_mcp_access(
                        user_id=user.id,
                        tenant_id=g.current_tenant.id if hasattr(g, 'current_tenant') else agent.department.tenant_id,
                        agent_id=agent.id,
                        integration=outlook_integration,
                        status='success',
                        ip_address=request.remote_addr if request else None
                    )

                    mcp_servers.append({
                        'name': f'outlook_{outlook_integration.owner_type}',
                        'integration_id': outlook_integration.id,
                        'mcp_process_name': outlook_integration.get_mcp_process_name(),
                        'tools': ['outlook_list', 'outlook_read', 'outlook_send', 'outlook_search']
                    })

        # Google Drive MCP
        if agent.enable_google_drive:
            drive_integration = None

            # Check workspace Drive first (always accessible)
            drive_workspace = Integration.query.filter_by(
                tenant_id=agent.department.tenant_id,
                integration_type='google_drive',
                owner_type='tenant',
                owner_id=agent.department.tenant_id,
                is_active=True
            ).first()

            if drive_workspace:
                drive_integration = drive_workspace
            elif can_access_personal:
                # Only check personal if user created this agent
                drive_personal = Integration.query.filter_by(
                    tenant_id=agent.department.tenant_id,
                    integration_type='google_drive',
                    owner_type='user',
                    owner_id=user.id,
                    is_active=True
                ).first()
                drive_integration = drive_personal
            else:
                # Log denied access attempt
                current_app.logger.warning(
                    f"MCP_ACCESS_DENIED: user={user.id} agent={agent.id} "
                    f"integration_type=google_drive reason=agent_not_created_by_user"
                )
                AuditLog.log_access_denied(
                    user_id=user.id,
                    tenant_id=g.current_tenant.id if hasattr(g, 'current_tenant') else agent.department.tenant_id,
                    resource_type='integration',
                    resource_id=None,
                    reason='Personal Drive access denied - agent not created by user',
                    agent_id=agent.id,
                    ip_address=request.remote_addr if request else None
                )

            if drive_integration:
                status = mcp_manager.get_process_status(drive_integration)
                if status.get('running'):
                    # Log successful MCP access
                    AuditLog.log_mcp_access(
                        user_id=user.id,
                        tenant_id=g.current_tenant.id if hasattr(g, 'current_tenant') else agent.department.tenant_id,
                        agent_id=agent.id,
                        integration=drive_integration,
                        status='success',
                        ip_address=request.remote_addr if request else None
                    )

                    mcp_servers.append({
                        'name': f'drive_{drive_integration.owner_type}',
                        'integration_id': drive_integration.id,
                        'mcp_process_name': drive_integration.get_mcp_process_name(),
                        'tools': ['drive_list', 'drive_read', 'drive_write', 'drive_search', 'drive_create']
                    })

        return mcp_servers if mcp_servers else None

    def _get_mcp_tools(self, agent, user) -> Optional[List[Dict]]:
        """
        Get Claude-compatible tool definitions from enabled MCP integrations

        Args:
            agent: Agent model with integration flags
            user: User model for checking access

        Returns:
            List of tool definitions, or None if no tools available
        """
        from app.models.integration import Integration
        from app.services.mcp_client import get_mcp_tools_for_integration

        all_tools = []
        mcp_servers = self._build_mcp_config(agent, user)

        if not mcp_servers:
            return None

        # Collect tools from all enabled integrations
        for server_config in mcp_servers:
            integration_id = server_config.get('integration_id')
            if not integration_id:
                continue

            integration = Integration.query.get(integration_id)
            if not integration:
                continue

            tools = get_mcp_tools_for_integration(integration)
            if tools:
                all_tools.extend(tools)
                current_app.logger.info(f"Loaded {len(tools)} tools from {integration.integration_type}")

        return all_tools if all_tools else None

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
        agent=None,
        user=None
    ) -> str:
        """
        Send a chat message to Claude and get a response.
        Supports MCP tool calling for external data access.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt defining the agent's behavior
            model: Model to use (defaults to Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            agent: Agent model (for MCP integration support)
            user: User model (for MCP integration support)

        Returns:
            The AI's response text
        """
        if model is None:
            model = self.DEFAULT_MODEL

        try:
            # Build API call parameters
            api_params = {
                'model': model,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'system': system_prompt,
                'messages': messages
            }

            # Get MCP tools if agent has integrations enabled
            tools = None
            if agent and user:
                tools = self._get_mcp_tools(agent, user)
                if tools:
                    api_params['tools'] = tools
                    current_app.logger.info(f"Agent {agent.name} has {len(tools)} tools available")

            # Call Claude API (potentially multiple times for tool use)
            response = self.client.messages.create(**api_params)

            # Handle tool use loop
            while response.stop_reason == "tool_use":
                # Extract tool calls from response
                tool_uses = [block for block in response.content if block.type == "tool_use"]

                if not tool_uses:
                    break

                # Add assistant's response to message history
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute tools and collect results
                tool_results = []
                for tool_use in tool_uses:
                    try:
                        result = self._execute_mcp_tool(
                            tool_name=tool_use.name,
                            tool_input=tool_use.input,
                            agent=agent,
                            user=user
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result) if not isinstance(result, str) else result
                        })
                        current_app.logger.info(f"Tool {tool_use.name} executed successfully")
                    except Exception as e:
                        current_app.logger.error(f"Tool {tool_use.name} failed: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "is_error": True,
                            "content": f"Error executing tool: {str(e)}"
                        })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Update api_params with new messages
                api_params['messages'] = messages

                # Get next response from Claude
                response = self.client.messages.create(**api_params)

            # Extract final text response
            text_blocks = [block.text for block in response.content if hasattr(block, 'text')]
            if text_blocks:
                return "\n".join(text_blocks)

            return "I apologize, but I couldn't generate a response. Please try again."

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            raise

    def _execute_mcp_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute an MCP tool call

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters
            agent: Agent making the request
            user: User context

        Returns:
            Tool execution result
        """
        # TODO: Implement actual MCP tool execution via stdio
        # For now, return mock data based on tool name

        current_app.logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

        if "list_emails" in tool_name:
            return {
                "emails": [
                    {
                        "id": "email_1",
                        "subject": "Welcome to Outlook",
                        "from": "welcome@microsoft.com",
                        "date": "2025-11-14",
                        "preview": "Get started with your new Outlook account..."
                    },
                    {
                        "id": "email_2",
                        "subject": "Your weekly summary",
                        "from": "noreply@company.com",
                        "date": "2025-11-13",
                        "preview": "Here's what happened this week..."
                    }
                ],
                "total": 2
            }

        elif "read_email" in tool_name:
            email_id = tool_input.get("email_id")
            return {
                "id": email_id,
                "subject": "Sample Email",
                "from": "sender@example.com",
                "date": "2025-11-14",
                "body": "This is the email body content. It contains important information about your account."
            }

        elif "search" in tool_name:
            query = tool_input.get("query", "")
            return {
                "results": [
                    {
                        "id": "result_1",
                        "subject": f"Email matching '{query}'",
                        "snippet": f"This email contains the keyword: {query}"
                    }
                ],
                "total": 1
            }

        elif "calendar" in tool_name:
            return {
                "events": [
                    {
                        "id": "event_1",
                        "title": "Team Meeting",
                        "start": "2025-11-15T10:00:00",
                        "end": "2025-11-15T11:00:00",
                        "location": "Conference Room A"
                    }
                ],
                "total": 1
            }

        return {"error": "Tool not implemented", "tool": tool_name}

    def analyze_bug_screenshot(
        self,
        image_base64: str,
        image_media_type: str = "image/png",
        current_url: Optional[str] = None,
        tenant_name: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Analyze a bug screenshot using Claude's vision capabilities.

        Args:
            image_base64: Base64 encoded image data (without data URI prefix)
            image_media_type: Image MIME type (e.g., 'image/png', 'image/jpeg')
            current_url: The URL where the bug occurred
            tenant_name: Name of the workspace/tenant
            user_name: Name of the user reporting the bug

        Returns:
            Dictionary with 'subject', 'description', and 'priority'
        """
        # Build context information
        context_parts = []
        if tenant_name:
            context_parts.append(f"Workspace: {tenant_name}")
        if user_name:
            context_parts.append(f"Reporter: {user_name}")
        if current_url:
            context_parts.append(f"Page URL: {current_url}")

        context = "\n".join(context_parts) if context_parts else "No additional context provided."

        system_prompt = f"""You are a helpful assistant analyzing screenshots for bug reports in the Soloquy application - a Slack-inspired team collaboration platform.

{context}

Analyze the screenshot and provide a structured bug report. Look for:
1. Error messages, broken UI elements, or unexpected behavior
2. Layout issues, misalignments, or styling problems
3. Missing or incorrect data display
4. Navigation or interaction problems

Respond ONLY with valid JSON in this exact format:
{{
  "subject": "Brief, clear title for the bug (max 80 chars)",
  "description": "Detailed description including:\\n- What you observe in the screenshot\\n- What appears to be wrong\\n- Any error messages visible\\n- Steps that likely led to this state (if discernible)",
  "priority": "low|medium|high|urgent"
}}

Priority guidelines:
- low: Cosmetic issues, minor text problems
- medium: Functionality works but has issues, has workarounds
- high: Major functionality broken, significantly impacts user experience
- urgent: Critical system failure, data loss, security issue, app completely broken"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Use Sonnet for vision support
                max_tokens=1024,
                temperature=0.3,  # Lower temperature for more consistent analysis
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": "Please analyze this screenshot and provide a bug report in the requested JSON format."
                        }
                    ]
                }]
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                response_text = response.content[0].text.strip()

                # Try to parse JSON from response
                # Sometimes Claude adds markdown code blocks, so we need to extract the JSON
                if "```json" in response_text:
                    # Extract JSON from markdown code block
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    # Extract from generic code block
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()

                # Parse the JSON
                result = json.loads(response_text)

                # Validate the response has required fields
                if not all(key in result for key in ['subject', 'description', 'priority']):
                    raise ValueError("AI response missing required fields")

                # Validate priority value
                if result['priority'] not in ['low', 'medium', 'high', 'urgent']:
                    result['priority'] = 'medium'  # Default to medium if invalid

                return result

            # Fallback if no response
            return {
                'subject': 'Bug Report from Screenshot',
                'description': 'Please review the attached screenshot and provide details about the issue.',
                'priority': 'medium'
            }

        except json.JSONDecodeError as e:
            print(f"Error parsing AI response as JSON: {e}")
            # Return fallback response
            return {
                'subject': 'Bug Report from Screenshot',
                'description': 'AI analysis encountered an error. Please describe the issue shown in the screenshot.',
                'priority': 'medium'
            }
        except Exception as e:
            print(f"Error analyzing screenshot with Claude API: {e}")
            raise

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
        agent=None,
        user=None
    ):
        """
        Stream a chat response from Claude.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt defining the agent's behavior
            model: Model to use (defaults to Haiku)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            agent: Agent model (for MCP integration support)
            user: User model (for MCP integration support)

        Yields:
            Text chunks as they arrive from the API
        """
        if model is None:
            model = self.DEFAULT_MODEL

        try:
            # Build API call parameters
            stream_params = {
                'model': model,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'system': system_prompt,
                'messages': messages
            }

            # Add MCP context to system prompt if agent has MCP integrations enabled
            if agent and user:
                mcp_servers = self._build_mcp_config(agent, user)
                if mcp_servers:
                    # Append MCP availability info to system prompt
                    mcp_info = "\n\nAvailable MCP Integrations:\n"
                    for server in mcp_servers:
                        mcp_info += f"- {server['name']}: {', '.join(server['tools'])}\n"
                    stream_params['system'] = system_prompt + mcp_info

                    # Log MCP context for debugging
                    current_app.logger.info(f"Agent {agent.name} streaming with MCP: {[s['name'] for s in mcp_servers]}")

            with self.client.messages.stream(**stream_params) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            print(f"Error streaming from Claude API: {e}")
            raise


# Singleton instance
_ai_service = None

def get_ai_service() -> AIService:
    """Get or create the AI service singleton"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
