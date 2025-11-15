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

    def _get_outlook_tools(self) -> List[Dict]:
        """
        Get static Outlook tool definitions for direct Graph API calls

        Returns:
            List of Outlook tool definitions
        """
        return [
            {
                "name": "outlook_list_emails",
                "description": "List recent emails from Outlook inbox",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of emails to return (default: 10)",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "outlook_read_email",
                "description": "Read the full content of a specific email by ID",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "The ID of the email to read"
                        }
                    },
                    "required": ["email_id"]
                }
            },
            {
                "name": "outlook_search_emails",
                "description": "Search emails by keyword in subject or body",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text"
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum results to return (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "outlook_send_email",
                "description": "Compose and send a new email",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of recipient email addresses"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content"
                        },
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of CC recipients"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        ]

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

            # Get Outlook tools if agent has Outlook enabled
            tools = None
            if agent and user and agent.enable_outlook:
                print(f"[OUTLOOK] Getting Outlook tools for agent {agent.id}")
                tools = self._get_outlook_tools()
                print(f"[OUTLOOK] Got {len(tools)} Outlook tools")
                if tools:
                    api_params['tools'] = tools
                    current_app.logger.info(f"Agent {agent.name} has {len(tools)} Outlook tools available")

            # Call Claude API (potentially multiple times for tool use)
            response = self.client.messages.create(**api_params)
            print(f"[MCP DEBUG] Claude response stop_reason: {response.stop_reason}")

            # Handle tool use loop
            while response.stop_reason == "tool_use":
                # Extract tool calls from response
                tool_uses = [block for block in response.content if block.type == "tool_use"]
                print(f"[MCP DEBUG] Claude wants to use {len(tool_uses)} tools")

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
                    print(f"[OUTLOOK] Executing tool: {tool_use.name} with input: {tool_use.input}")
                    try:
                        result = self._execute_outlook_tool(
                            tool_name=tool_use.name,
                            tool_input=tool_use.input,
                            agent=agent,
                            user=user
                        )
                        print(f"[OUTLOOK] Tool {tool_use.name} returned: {result}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result) if not isinstance(result, str) else result
                        })
                        current_app.logger.info(f"Tool {tool_use.name} executed successfully")
                    except Exception as e:
                        print(f"[MCP DEBUG] Tool {tool_use.name} failed with error: {e}")
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

    def _execute_outlook_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute Outlook tool using direct Microsoft Graph API

        Args:
            tool_name: Name of the tool (outlook_list_emails, etc.)
            tool_input: Tool input parameters
            agent: Agent making the request
            user: User context

        Returns:
            Tool execution result
        """
        from app.services.outlook_service import OutlookGraphService
        from app.models.integration import Integration

        print(f"[OUTLOOK] Executing tool: {tool_name} with input: {tool_input}")

        # Find Outlook integration
        integration = None
        if agent.created_by_id == user.id:
            integration = Integration.query.filter_by(
                integration_type='outlook',
                owner_type='user',
                owner_id=user.id,
                is_active=True
            ).first()

        if not integration:
            integration = Integration.query.filter_by(
                integration_type='outlook',
                owner_type='tenant',
                owner_id=agent.department.tenant_id,
                is_active=True
            ).first()

        if not integration or not integration.access_token:
            return {"error": "Outlook not connected. Please connect your Outlook account in Settings > Integrations."}

        # Create Outlook service with access token
        outlook = OutlookGraphService(integration.access_token)

        try:
            # Route to appropriate method
            if tool_name == 'outlook_list_emails':
                max_results = tool_input.get('max_results', 10)
                emails = outlook.list_emails(max_results=max_results)
                return {"emails": emails, "count": len(emails)}

            elif tool_name == 'outlook_read_email':
                email_id = tool_input.get('email_id')
                if not email_id:
                    return {"error": "email_id parameter is required"}
                email = outlook.read_email(email_id)
                return {"email": email}

            elif tool_name == 'outlook_search_emails':
                query = tool_input.get('query')
                if not query:
                    return {"error": "query parameter is required"}
                max_results = tool_input.get('max_results', 10)
                emails = outlook.search_emails(query, max_results=max_results)
                return {"emails": emails, "count": len(emails)}

            elif tool_name == 'outlook_send_email':
                to = tool_input.get('to', [])
                subject = tool_input.get('subject', '')
                body = tool_input.get('body', '')
                cc = tool_input.get('cc')

                if not to or not isinstance(to, list):
                    return {"error": "to parameter must be a list of email addresses"}

                result = outlook.send_email(to, subject, body, cc=cc)
                return result

            else:
                return {"error": f"Unknown Outlook tool: {tool_name}"}

        except Exception as e:
            current_app.logger.error(f"Error executing Outlook tool {tool_name}: {e}")
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

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
