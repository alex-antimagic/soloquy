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
            },
            {
                "name": "outlook_list_calendar_events",
                "description": "List upcoming calendar events from Outlook calendar",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of events to return (default: 10)",
                            "default": 10
                        },
                        "days_ahead": {
                            "type": "number",
                            "description": "Number of days ahead to look for events (default: 7)",
                            "default": 7
                        }
                    }
                }
            },
            {
                "name": "outlook_create_calendar_event",
                "description": "Create a new calendar event in Outlook calendar",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": "Event title"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in ISO format WITHOUT timezone (e.g., '2024-01-15T14:00:00'). The AI should convert user's local time to UTC before passing here."
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in ISO format WITHOUT timezone. The AI should convert user's local time to UTC before passing here."
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of attendee email addresses"
                        },
                        "location": {
                            "type": "string",
                            "description": "Optional location string"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional event description"
                        },
                        "is_online_meeting": {
                            "type": "boolean",
                            "description": "Whether to create a Teams online meeting (default: False)",
                            "default": False
                        }
                    },
                    "required": ["subject", "start", "end"]
                }
            },
            {
                "name": "outlook_get_free_busy",
                "description": "Check free/busy availability for one or more people",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of email addresses to check availability for"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in ISO format"
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in ISO format"
                        }
                    },
                    "required": ["emails", "start", "end"]
                }
            }
        ]

    def _get_website_tools(self) -> List[Dict]:
        """
        Get website builder tool definitions for AI agents

        Returns:
            List of website builder tool definitions
        """
        return [
            {
                "name": "website_generate",
                "description": "Generate a complete website from business context. Creates homepage, about page, and theme based on the tenant's business information.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "regenerate": {
                            "type": "boolean",
                            "description": "Force regeneration even if website exists (default: false)",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "website_create_page",
                "description": "Create a new page on the website",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "description": "Type of page: 'home', 'blog', 'landing', or 'custom'",
                            "enum": ["home", "blog", "landing", "custom"]
                        },
                        "slug": {
                            "type": "string",
                            "description": "URL slug for the page (e.g., 'about-us', 'pricing')"
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title"
                        },
                        "content_description": {
                            "type": "string",
                            "description": "Description of what content should be on the page. The AI will generate appropriate sections."
                        },
                        "publish": {
                            "type": "boolean",
                            "description": "Publish the page immediately (default: false)",
                            "default": False
                        }
                    },
                    "required": ["page_type", "slug", "title", "content_description"]
                }
            },
            {
                "name": "website_update_theme",
                "description": "Update the website theme colors and fonts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "primary_color": {
                            "type": "string",
                            "description": "Primary brand color (hex code, e.g., '#667eea')"
                        },
                        "secondary_color": {
                            "type": "string",
                            "description": "Secondary color (hex code)"
                        },
                        "background_color": {
                            "type": "string",
                            "description": "Background color (hex code)"
                        },
                        "text_color": {
                            "type": "string",
                            "description": "Text color (hex code)"
                        },
                        "heading_font": {
                            "type": "string",
                            "description": "Google Font name for headings (e.g., 'Inter', 'Roboto')"
                        },
                        "body_font": {
                            "type": "string",
                            "description": "Google Font name for body text"
                        }
                    }
                }
            },
            {
                "name": "website_publish",
                "description": "Publish or unpublish the website",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "publish": {
                            "type": "boolean",
                            "description": "True to publish, false to unpublish"
                        },
                        "is_indexable": {
                            "type": "boolean",
                            "description": "Allow search engines to index the website (default: true)",
                            "default": True
                        }
                    },
                    "required": ["publish"]
                }
            },
            {
                "name": "website_get_status",
                "description": "Get the current status and details of the website",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def _get_competitive_analysis_tools(self) -> List[Dict]:
        """
        Get competitive analysis tool definitions for AI agents

        Returns:
            List of competitive analysis tool definitions
        """
        return [
            {
                "name": "competitive_analysis_suggest_competitors",
                "description": "Suggest competitor companies based on workspace business context",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of competitors to suggest (default: 10)",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "competitive_analysis_analyze",
                "description": "Run comprehensive competitive analysis comparing workspace against specified competitors",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "competitor_ids": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "CompetitorProfile IDs to analyze (use after suggesting competitors)"
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["comprehensive", "website", "marketing"],
                            "description": "Type of analysis to perform",
                            "default": "comprehensive"
                        }
                    },
                    "required": ["competitor_ids"]
                }
            },
            {
                "name": "competitive_analysis_get_status",
                "description": "Get status and results of the most recent competitive analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def _get_file_generation_tools(self) -> List[Dict]:
        """
        Get file generation tool definitions for AI agents

        Returns:
            List of file generation tool definitions
        """
        return [
            {
                "name": "generate_pdf_report",
                "description": "Generate a PDF report with formatted content including tables, headings, and paragraphs",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Report title"
                        },
                        "content_blocks": {
                            "type": "array",
                            "description": "List of content blocks (headings, paragraphs, tables, spacers)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["heading", "paragraph", "table", "spacer"],
                                        "description": "Type of content block"
                                    },
                                    "content": {
                                        "description": "Content for the block. For tables, use {headers: [...], data: [[...]]}. For text/headings, use string."
                                    },
                                    "level": {
                                        "type": "number",
                                        "description": "Heading level (1-3, only for heading type)"
                                    },
                                    "height": {
                                        "type": "number",
                                        "description": "Height in inches (only for spacer type)"
                                    }
                                }
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["title", "content_blocks"]
                }
            },
            {
                "name": "export_to_csv",
                "description": "Export tabular data to a CSV file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "headers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column headers"
                        },
                        "data": {
                            "type": "array",
                            "description": "Array of rows, where each row is an array of values",
                            "items": {
                                "type": "array"
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["headers", "data"]
                }
            },
            {
                "name": "create_spreadsheet",
                "description": "Create an Excel spreadsheet (.xlsx) with one or more sheets",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sheets": {
                            "type": "array",
                            "description": "Array of sheet definitions",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Sheet name"
                                    },
                                    "headers": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Column headers"
                                    },
                                    "data": {
                                        "type": "array",
                                        "description": "Array of rows",
                                        "items": {"type": "array"}
                                    }
                                }
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["sheets"]
                }
            },
            {
                "name": "create_markdown_document",
                "description": "Create a Markdown document (.md) with formatted text, headers, lists, code blocks, and tables",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content including headers (##), lists (- or 1.), bold (**text**), code blocks (```), tables, etc."
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional document title (will be added as H1 at the top)"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "create_word_document",
                "description": "Create a Word document (.docx) with formatted content including headings, paragraphs, bullet lists, numbered lists, and tables",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Document title"
                        },
                        "content_blocks": {
                            "type": "array",
                            "description": "List of content blocks",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["heading", "paragraph", "bullet_list", "numbered_list", "table"],
                                        "description": "Type of content block"
                                    },
                                    "content": {
                                        "description": "Content for the block. For lists, use array of strings. For tables, use {headers: [...], data: [[...]]}. For text/headings, use string."
                                    },
                                    "level": {
                                        "type": "number",
                                        "description": "Heading level (1-3, only for heading type)"
                                    }
                                }
                            }
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (auto-generated if not provided)"
                        }
                    },
                    "required": ["title", "content_blocks"]
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

            # Get tools if agent has integrations enabled
            tools = []
            if agent and user:
                if agent.enable_outlook:
                    print(f"[OUTLOOK] Getting Outlook tools for agent {agent.id}")
                    outlook_tools = self._get_outlook_tools()
                    print(f"[OUTLOOK] Got {len(outlook_tools)} Outlook tools")
                    tools.extend(outlook_tools)

                if agent.enable_website_builder:
                    print(f"[WEBSITE] Getting Website tools for agent {agent.id}")
                    website_tools = self._get_website_tools()
                    print(f"[WEBSITE] Got {len(website_tools)} Website tools")
                    tools.extend(website_tools)

                if agent.enable_file_generation:
                    print(f"[FILE_GEN] Getting File Generation tools for agent {agent.id}")
                    file_gen_tools = self._get_file_generation_tools()
                    print(f"[FILE_GEN] Got {len(file_gen_tools)} File Generation tools")
                    tools.extend(file_gen_tools)

                if agent.enable_competitive_analysis:
                    print(f"[COMPETITIVE] Getting Competitive Analysis tools for agent {agent.id}")
                    competitive_tools = self._get_competitive_analysis_tools()
                    print(f"[COMPETITIVE] Got {len(competitive_tools)} Competitive Analysis tools")
                    tools.extend(competitive_tools)

                if tools:
                    api_params['tools'] = tools
                    current_app.logger.info(f"Agent {agent.name} has {len(tools)} tools available")

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
                    print(f"[TOOL] Executing tool: {tool_use.name} with input: {tool_use.input}")
                    try:
                        # Route to appropriate tool executor
                        if tool_use.name.startswith('outlook_'):
                            result = self._execute_outlook_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('website_'):
                            result = self._execute_website_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name in ['generate_pdf_report', 'export_to_csv', 'create_spreadsheet', 'create_markdown_document', 'create_word_document']:
                            result = self._execute_file_generation_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        elif tool_use.name.startswith('competitive_analysis_'):
                            result = self._execute_competitive_analysis_tool(
                                tool_name=tool_use.name,
                                tool_input=tool_use.input,
                                agent=agent,
                                user=user
                            )
                        else:
                            result = {"error": f"Unknown tool: {tool_use.name}"}

                        print(f"[TOOL] Tool {tool_use.name} returned: {result}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result) if not isinstance(result, str) else result
                        })
                        current_app.logger.info(f"Tool {tool_use.name} executed successfully")
                    except Exception as e:
                        print(f"[TOOL] Tool {tool_use.name} failed with error: {e}")
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

        # Check if token needs refresh
        if integration.needs_refresh():
            try:
                print(f"[OUTLOOK] Token needs refresh for integration {integration.id}")
                OutlookGraphService.refresh_access_token(integration)
                print(f"[OUTLOOK] Token refreshed successfully")
            except Exception as e:
                error_msg = f"Failed to refresh Outlook token: {str(e)}"
                print(f"[OUTLOOK] {error_msg}")
                return {"error": error_msg}

        # Create Outlook service with access token and integration for auto-refresh
        outlook = OutlookGraphService(integration.access_token, integration=integration)

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

            elif tool_name == 'outlook_list_calendar_events':
                max_results = tool_input.get('max_results', 10)
                days_ahead = tool_input.get('days_ahead', 7)
                events = outlook.list_calendar_events(max_results=max_results, days_ahead=days_ahead)
                return {"events": events, "count": len(events)}

            elif tool_name == 'outlook_create_calendar_event':
                subject = tool_input.get('subject')
                start = tool_input.get('start')
                end = tool_input.get('end')
                attendees = tool_input.get('attendees')
                location = tool_input.get('location')
                body = tool_input.get('body')
                is_online_meeting = tool_input.get('is_online_meeting', False)

                if not all([subject, start, end]):
                    return {"error": "subject, start, and end parameters are required"}

                result = outlook.create_calendar_event(
                    subject=subject,
                    start=start,
                    end=end,
                    attendees=attendees,
                    location=location,
                    body=body,
                    is_online_meeting=is_online_meeting
                )
                return result

            elif tool_name == 'outlook_get_free_busy':
                emails = tool_input.get('emails', [])
                start = tool_input.get('start')
                end = tool_input.get('end')

                if not emails or not isinstance(emails, list):
                    return {"error": "emails parameter must be a list of email addresses"}

                if not all([start, end]):
                    return {"error": "start and end parameters are required"}

                result = outlook.get_free_busy(emails=emails, start=start, end=end)
                return {"availability": result}

            else:
                return {"error": f"Unknown Outlook tool: {tool_name}"}

        except Exception as e:
            current_app.logger.error(f"Error executing Outlook tool {tool_name}: {e}")
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

    def _execute_website_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute website builder tool

        Args:
            tool_name: Name of the tool (website_generate, etc.)
            tool_input: Tool input parameters
            agent: Agent making the request
            user: User context

        Returns:
            Tool execution result
        """
        from app.services.website_generator_service import website_generator
        from app.models.website import Website, WebsitePage, WebsiteTheme
        from app.models.tenant import Tenant
        from app import db
        from datetime import datetime

        print(f"[WEBSITE] Executing tool: {tool_name} with input: {tool_input}")

        # Get tenant from agent's department
        tenant = agent.department.tenant

        try:
            # Route to appropriate method
            if tool_name == 'website_generate':
                regenerate = tool_input.get('regenerate', False)

                # Check if website exists
                existing = Website.query.filter_by(tenant_id=tenant.id).first()
                if existing and not regenerate:
                    return {
                        "success": False,
                        "message": "Website already exists. Use regenerate=true to force regeneration.",
                        "website_url": f"/w/{tenant.slug}"
                    }

                # Generate website
                website = website_generator.generate_website_for_tenant(tenant, agent_id=agent.id)
                db.session.commit()

                return {
                    "success": True,
                    "message": "Website generated successfully",
                    "website_url": f"/w/{tenant.slug}",
                    "pages_created": website.pages.count(),
                    "is_published": website.is_published
                }

            elif tool_name == 'website_create_page':
                page_type = tool_input.get('page_type')
                slug = tool_input.get('slug')
                title = tool_input.get('title')
                content_description = tool_input.get('content_description')
                publish = tool_input.get('publish', False)

                # Validate inputs
                if not all([page_type, slug, title, content_description]):
                    return {"error": "Missing required parameters"}

                # Get or create website
                website = Website.query.filter_by(tenant_id=tenant.id).first()
                if not website:
                    return {"error": "No website found. Use website_generate first."}

                # Check if slug already exists
                existing = WebsitePage.query.filter_by(website_id=website.id, slug=slug).first()
                if existing:
                    return {"error": f"Page with slug '{slug}' already exists"}

                # Generate page content using AI
                prompt = f"""Create page content for: {title}

Page Type: {page_type}
Description: {content_description}

Generate a JSON structure with appropriate sections for this page type.
For landing pages, include hero, features, and CTA sections.
For blog posts, include title, author, date, content sections.
For custom pages, create relevant content sections based on the description.

Return ONLY valid JSON in this format:
{{
    "sections": [
        {{"type": "hero", "heading": "...", "subheading": "...", "cta_text": "...", "cta_url": "..."}},
        {{"type": "text", "heading": "...", "content": "<p>HTML content</p>"}}
    ]
}}"""

                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    temperature=0.8,
                    messages=[{"role": "user", "content": prompt}]
                )

                # Extract JSON from response
                content = response.content[0].text
                if '{' in content and '}' in content:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    json_str = content[json_start:json_end]
                    content_json = json.loads(json_str)
                else:
                    content_json = {"sections": [{"type": "text", "heading": title, "content": f"<p>{content_description}</p>"}]}

                # Create page
                page = WebsitePage(
                    website_id=website.id,
                    page_type=page_type,
                    slug=slug,
                    title=title,
                    meta_description=content_description[:160],
                    content_json=content_json,
                    is_published=publish,
                    agent_id=agent.id,
                    created_by_id=user.id
                )

                if publish:
                    page.published_at = datetime.utcnow()

                db.session.add(page)
                db.session.commit()

                return {
                    "success": True,
                    "message": f"Page '{title}' created successfully",
                    "page_url": f"/w/{tenant.slug}/{slug}" if slug else f"/w/{tenant.slug}",
                    "is_published": publish
                }

            elif tool_name == 'website_update_theme':
                # Get website
                website = Website.query.filter_by(tenant_id=tenant.id).first()
                if not website:
                    return {"error": "No website found. Use website_generate first."}

                # Get or create theme
                if not website.theme:
                    theme = WebsiteTheme(website=website)
                    db.session.add(theme)
                else:
                    theme = website.theme

                # Update theme properties
                if 'primary_color' in tool_input:
                    theme.primary_color = tool_input['primary_color']
                if 'secondary_color' in tool_input:
                    theme.secondary_color = tool_input['secondary_color']
                if 'background_color' in tool_input:
                    theme.background_color = tool_input['background_color']
                if 'text_color' in tool_input:
                    theme.text_color = tool_input['text_color']
                if 'heading_font' in tool_input:
                    theme.heading_font = tool_input['heading_font']
                if 'body_font' in tool_input:
                    theme.body_font = tool_input['body_font']

                db.session.commit()

                return {
                    "success": True,
                    "message": "Theme updated successfully",
                    "theme": {
                        "primary_color": theme.primary_color,
                        "secondary_color": theme.secondary_color,
                        "background_color": theme.background_color,
                        "text_color": theme.text_color,
                        "heading_font": theme.heading_font,
                        "body_font": theme.body_font
                    }
                }

            elif tool_name == 'website_publish':
                publish = tool_input.get('publish')
                is_indexable = tool_input.get('is_indexable', True)

                if publish is None:
                    return {"error": "publish parameter is required"}

                # Get website
                website = Website.query.filter_by(tenant_id=tenant.id).first()
                if not website:
                    return {"error": "No website found. Use website_generate first."}

                # Update publishing status
                website.is_published = publish
                website.is_indexable = is_indexable

                if publish and not website.published_at:
                    website.published_at = datetime.utcnow()

                db.session.commit()

                return {
                    "success": True,
                    "message": f"Website {'published' if publish else 'unpublished'} successfully",
                    "is_published": website.is_published,
                    "is_indexable": website.is_indexable,
                    "website_url": f"/w/{tenant.slug}"
                }

            elif tool_name == 'website_get_status':
                # Get website
                website = Website.query.filter_by(tenant_id=tenant.id).first()

                if not website:
                    return {
                        "exists": False,
                        "message": "No website found. Use website_generate to create one."
                    }

                # Get pages
                pages = website.pages.all()
                published_pages = [p for p in pages if p.is_published]

                return {
                    "exists": True,
                    "is_published": website.is_published,
                    "is_indexable": website.is_indexable,
                    "website_url": f"/w/{tenant.slug}",
                    "total_pages": len(pages),
                    "published_pages": len(published_pages),
                    "pages": [
                        {
                            "title": p.title,
                            "slug": p.slug,
                            "type": p.page_type,
                            "is_published": p.is_published,
                            "views": p.view_count
                        }
                        for p in pages
                    ],
                    "theme": {
                        "primary_color": website.theme.primary_color if website.theme else None,
                        "secondary_color": website.theme.secondary_color if website.theme else None
                    } if website.theme else None
                }

            else:
                return {"error": f"Unknown website tool: {tool_name}"}

        except Exception as e:
            current_app.logger.error(f"Error executing website tool {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

    def _execute_file_generation_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute file generation tool

        Args:
            tool_name: Name of the tool (generate_pdf_report, export_to_csv, create_spreadsheet, create_markdown_document, create_word_document)
            tool_input: Tool input parameters
            agent: Agent model
            user: User model

        Returns:
            Result dictionary with file URL and metadata or error
        """
        from app.services.file_generation_service import FileGenerationService
        from app.models.generated_file import GeneratedFile
        from app import db

        print(f"[FILE_GEN] Executing tool: {tool_name}")
        print(f"[FILE_GEN] Input keys: {list(tool_input.keys())}")

        try:
            # Get tenant from agent's department
            if not agent or not agent.department:
                print(f"[FILE_GEN] ERROR: No workspace context available")
                return {"error": "No workspace context available"}

            tenant = agent.department.tenant
            print(f"[FILE_GEN] Tenant: {tenant.name} (ID: {tenant.id})")
            file_gen_service = FileGenerationService()

            if tool_name == "generate_pdf_report":
                # Generate PDF report
                title = tool_input.get('title')
                content_blocks = tool_input.get('content_blocks', [])
                filename = tool_input.get('filename')

                result = file_gen_service.generate_pdf(
                    title=title,
                    content_blocks=content_blocks,
                    tenant_id=tenant.id,
                    filename=filename
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='report',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"PDF report '{result['filename']}' generated successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to generate PDF')}

            elif tool_name == "export_to_csv":
                # Export to CSV
                headers = tool_input.get('headers', [])
                data = tool_input.get('data', [])
                filename = tool_input.get('filename')

                print(f"[FILE_GEN] Generating CSV with {len(headers)} headers and {len(data)} rows")
                print(f"[FILE_GEN] Filename: {filename}")

                result = file_gen_service.generate_csv(
                    headers=headers,
                    data=data,
                    tenant_id=tenant.id,
                    filename=filename
                )

                print(f"[FILE_GEN] CSV generation result: success={result.get('success')}")

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='export',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"CSV file '{result['filename']}' exported successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to export CSV')}

            elif tool_name == "create_spreadsheet":
                # Create Excel spreadsheet
                sheets = tool_input.get('sheets', [])
                filename = tool_input.get('filename')

                result = file_gen_service.generate_excel(
                    sheets=sheets,
                    tenant_id=tenant.id,
                    filename=filename
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='export',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"Excel file '{result['filename']}' created successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to create spreadsheet')}

            elif tool_name == "create_markdown_document":
                # Create Markdown document
                content = tool_input.get('content', '')
                title = tool_input.get('title')
                filename = tool_input.get('filename')

                result = file_gen_service.generate_markdown(
                    content=content,
                    tenant_id=tenant.id,
                    filename=filename,
                    title=title
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='document',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"Markdown document '{result['filename']}' created successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to create Markdown document')}

            elif tool_name == "create_word_document":
                # Create Word document
                title = tool_input.get('title', 'Document')
                content_blocks = tool_input.get('content_blocks', [])
                filename = tool_input.get('filename')

                result = file_gen_service.generate_docx(
                    title=title,
                    content_blocks=content_blocks,
                    tenant_id=tenant.id,
                    filename=filename
                )

                if result.get('success'):
                    # Save to database
                    generated_file = GeneratedFile(
                        tenant_id=tenant.id,
                        agent_id=agent.id if agent else None,
                        user_id=user.id,
                        filename=result['filename'],
                        file_type=result['file_type'],
                        mime_type=result['mime_type'],
                        file_size=result['file_size'],
                        file_purpose='document',
                        cloudinary_url=result['cloudinary_url'],
                        cloudinary_public_id=result['public_id']
                    )
                    db.session.add(generated_file)
                    db.session.commit()

                    return {
                        "success": True,
                        "message": f"Word document '{result['filename']}' created successfully",
                        "file_url": result['cloudinary_url'],
                        "file_id": generated_file.id,
                        "filename": result['filename'],
                        "file_size": result['file_size']
                    }
                else:
                    return {"error": result.get('error', 'Failed to create Word document')}

            else:
                return {"error": f"Unknown file generation tool: {tool_name}"}

        except Exception as e:
            error_msg = f"Error executing file generation tool {tool_name}: {str(e)}"
            print(f"[FILE_GEN] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to generate file: {str(e)}. Please check the file format and try again."}

    def _execute_competitive_analysis_tool(self, tool_name: str, tool_input: Dict, agent, user) -> Any:
        """
        Execute competitive analysis tool

        Args:
            tool_name: Name of the tool (competitive_analysis_suggest_competitors, competitive_analysis_analyze, competitive_analysis_get_status)
            tool_input: Tool input parameters
            agent: Agent model
            user: User model

        Returns:
            Result dictionary with competitive analysis data or error
        """
        from app.services.competitive_analysis_service import competitive_analysis_service
        from app.services.competitor_identification_service import competitor_identification_service
        from app.models.competitor_profile import CompetitorProfile
        from app import db

        print(f"[COMPETITIVE] Executing tool: {tool_name}")
        print(f"[COMPETITIVE] Input: {tool_input}")

        try:
            # Get tenant and website from agent's department
            if not agent or not agent.department:
                return {"error": "No workspace context available"}

            tenant = agent.department.tenant
            website = tenant.website

            if not website:
                return {"error": "No website configured for this workspace. Please set up a website first."}

            print(f"[COMPETITIVE] Tenant: {tenant.name}, Website ID: {website.id}")

            if tool_name == "competitive_analysis_suggest_competitors":
                # Suggest competitors based on workspace context
                limit = tool_input.get('limit', 10)

                suggestions = competitor_identification_service.suggest_competitors(
                    tenant_id=tenant.id,
                    limit=limit
                )

                # Create CompetitorProfile records for suggestions
                created_count = 0
                for suggestion in suggestions:
                    existing = CompetitorProfile.query.filter_by(
                        website_id=website.id,
                        domain=suggestion['website']
                    ).first()

                    if not existing:
                        competitor = CompetitorProfile(
                            website_id=website.id,
                            company_name=suggestion['name'],
                            domain=suggestion['website'],
                            is_confirmed=False,
                            suggested_by_agent=True,
                            confidence_score=suggestion.get('confidence', 0.8),
                            source=suggestion.get('source', 'ai_suggested')
                        )
                        db.session.add(competitor)
                        created_count += 1

                db.session.commit()

                # Get all competitors for this website
                all_competitors = CompetitorProfile.query.filter_by(website_id=website.id).all()
                competitor_list = [
                    {
                        'id': c.id,
                        'name': c.company_name,
                        'domain': c.domain,
                        'confidence': c.confidence_score,
                        'is_confirmed': c.is_confirmed
                    }
                    for c in all_competitors
                ]

                return {
                    "success": True,
                    "message": f"Found {len(suggestions)} potential competitors. Created {created_count} new competitor profiles.",
                    "competitors": competitor_list,
                    "total_count": len(competitor_list)
                }

            elif tool_name == "competitive_analysis_analyze":
                # Run competitive analysis
                competitor_ids = tool_input.get('competitor_ids', [])
                analysis_type = tool_input.get('analysis_type', 'comprehensive')

                if not competitor_ids:
                    return {"error": "Please provide at least one competitor ID to analyze"}

                # Create and run analysis
                analysis = competitive_analysis_service.create_analysis(
                    website_id=website.id,
                    competitor_ids=competitor_ids,
                    analysis_type=analysis_type,
                    agent_id=agent.id
                )

                # Check if analysis completed
                if analysis.status == 'completed':
                    return {
                        "success": True,
                        "status": "completed",
                        "analysis_id": analysis.id,
                        "message": f"Competitive analysis completed successfully. Analyzed {analysis.competitor_count} competitors.",
                        "executive_summary": analysis.executive_summary,
                        "strengths_count": len(json.loads(analysis.strengths)) if analysis.strengths else 0,
                        "gaps_count": len(json.loads(analysis.gaps)) if analysis.gaps else 0,
                        "opportunities_count": len(json.loads(analysis.opportunities)) if analysis.opportunities else 0
                    }
                elif analysis.status == 'failed':
                    return {
                        "success": False,
                        "status": "failed",
                        "message": f"Analysis failed: {analysis.executive_summary}"
                    }
                else:
                    return {
                        "success": True,
                        "status": analysis.status,
                        "analysis_id": analysis.id,
                        "message": "Analysis is in progress. This may take 5-10 minutes."
                    }

            elif tool_name == "competitive_analysis_get_status":
                # Get latest analysis status
                analysis = competitive_analysis_service.get_latest_analysis(website.id)

                if not analysis:
                    return {
                        "success": True,
                        "status": "not_started",
                        "message": "No competitive analysis has been run yet."
                    }

                if analysis.status == 'completed':
                    import json
                    strengths = json.loads(analysis.strengths) if analysis.strengths else []
                    gaps = json.loads(analysis.gaps) if analysis.gaps else []
                    opportunities = json.loads(analysis.opportunities) if analysis.opportunities else []

                    return {
                        "success": True,
                        "status": "completed",
                        "analysis_id": analysis.id,
                        "created_at": analysis.created_at.isoformat(),
                        "competitor_count": analysis.competitor_count,
                        "executive_summary": analysis.executive_summary,
                        "strengths": strengths[:3],  # Top 3 strengths
                        "gaps": gaps[:3],  # Top 3 gaps
                        "opportunities": opportunities[:3]  # Top 3 opportunities
                    }
                else:
                    return {
                        "success": True,
                        "status": analysis.status,
                        "analysis_id": analysis.id,
                        "message": f"Analysis is currently {analysis.status}"
                    }

            else:
                return {"error": f"Unknown competitive analysis tool: {tool_name}"}

        except Exception as e:
            error_msg = f"Error executing competitive analysis tool {tool_name}: {str(e)}"
            print(f"[COMPETITIVE] ERROR: {error_msg}")
            current_app.logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

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

    def detect_long_running_task(self, task_description: str, task_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Quickly detect if a task will take more than 20 seconds to complete.
        Uses Haiku for fast, cost-effective detection.

        Args:
            task_description: The task description to analyze
            task_context: Optional context (assigned_to, due_date, etc.)

        Returns:
            Dictionary with:
                - is_long_running: bool
                - estimated_duration_seconds: int
                - reasoning: str
                - complexity_score: int (1-10)
        """
        context_str = ""
        if task_context:
            context_parts = []
            if task_context.get('assigned_to'):
                context_parts.append(f"Assigned to: {task_context['assigned_to']}")
            if task_context.get('due_date'):
                context_parts.append(f"Due date: {task_context['due_date']}")
            if task_context.get('project'):
                context_parts.append(f"Project: {task_context['project']}")
            context_str = "\n".join(context_parts)

        system_prompt = """You are a task complexity analyzer. Your job is to quickly determine if a task will take more than 20 seconds for an AI agent to complete.

Consider these factors:
- Multi-step processes (research, analysis, code generation, testing)
- External API calls or data retrieval
- Complex calculations or transformations
- File generation (reports, documents, spreadsheets)
- Multiple related tasks that must be done together

Respond ONLY with valid JSON in this format:
{
  "is_long_running": true/false,
  "estimated_duration_seconds": <number>,
  "reasoning": "Brief explanation of your assessment",
  "complexity_score": <1-10>
}

Examples:
- "Send an email": ~5 seconds (simple API call)
- "Generate quarterly sales report": ~45 seconds (data aggregation + document generation)
- "Research competitors and create comparison matrix": ~120 seconds (web research + analysis + spreadsheet)
- "Update task status": ~3 seconds (simple database update)"""

        prompt = f"""Analyze this task and determine if it will take more than 20 seconds:

Task: {task_description}

{context_str}

Provide your assessment in the requested JSON format."""

        try:
            response = self.client.messages.create(
                model=self.DEFAULT_MODEL,  # Use Haiku for fast detection
                max_tokens=500,
                temperature=0.2,  # Low temperature for consistent analysis
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract and parse JSON response
            response_text = response.content[0].text.strip()

            # Handle markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            # Validate required fields
            required_fields = ['is_long_running', 'estimated_duration_seconds', 'reasoning', 'complexity_score']
            if not all(field in result for field in required_fields):
                raise ValueError("AI response missing required fields")

            return result

        except Exception as e:
            print(f"Error detecting long-running task: {e}")
            # Conservative fallback - assume it might be long-running
            return {
                'is_long_running': False,
                'estimated_duration_seconds': 15,
                'reasoning': 'Error during detection, defaulting to short task',
                'complexity_score': 5
            }

    def generate_execution_plan(
        self,
        task_description: str,
        task_id: int,
        agent_name: str,
        tenant_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate a detailed execution plan for a long-running task.
        Uses Sonnet for high-quality planning.

        Args:
            task_description: The task to plan
            task_id: ID of the task being planned
            agent_name: Name of the agent that will execute
            tenant_context: Optional tenant/workspace context

        Returns:
            Dictionary with:
                - steps: List[Dict] with step details
                - estimated_duration_minutes: int
                - requires_approval: bool
                - approval_reasoning: str
                - risks: List[str]
                - success_criteria: List[str]
        """
        context_str = "No additional context provided."
        if tenant_context:
            context_parts = []
            if tenant_context.get('tenant_name'):
                context_parts.append(f"Workspace: {tenant_context['tenant_name']}")
            if tenant_context.get('industry'):
                context_parts.append(f"Industry: {tenant_context['industry']}")
            if tenant_context.get('user_name'):
                context_parts.append(f"Requested by: {tenant_context['user_name']}")
            context_str = "\n".join(context_parts)

        system_prompt = f"""You are {agent_name}, an AI agent creating a detailed execution plan for a long-running task.

{context_str}

Your job is to:
1. Break down the task into clear, sequential steps
2. Estimate how long the entire task will take
3. Determine if user approval is needed before execution
4. Identify potential risks or issues
5. Define clear success criteria

Require approval for tasks that:
- Modify critical business data (financial records, customer data)
- Send external communications (emails, API calls to 3rd parties)
- Make irreversible changes (deletions, production deployments)
- Involve sensitive information or compliance concerns
- Have high business impact or cost implications

Do NOT require approval for:
- Read-only analysis and reporting
- Internal document generation
- Data aggregation and visualization
- Research and information gathering
- Development/testing tasks in non-production

Respond ONLY with valid JSON in this format:
{{
  "steps": [
    {{
      "step_number": 1,
      "title": "Brief step title",
      "description": "What will be done in this step",
      "estimated_duration_seconds": <number>,
      "dependencies": []
    }}
  ],
  "estimated_duration_minutes": <total minutes>,
  "requires_approval": true/false,
  "approval_reasoning": "Why approval is/isn't needed",
  "risks": ["risk 1", "risk 2"],
  "success_criteria": ["criterion 1", "criterion 2"]
}}"""

        prompt = f"""Create a detailed execution plan for this task:

Task ID: {task_id}
Task Description: {task_description}

Provide your plan in the requested JSON format."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Use Sonnet for planning
                max_tokens=2000,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract and parse JSON response
            response_text = response.content[0].text.strip()

            # Handle markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            # Validate required fields
            required_fields = ['steps', 'estimated_duration_minutes', 'requires_approval', 'approval_reasoning', 'risks', 'success_criteria']
            if not all(field in result for field in required_fields):
                raise ValueError("AI response missing required fields")

            return result

        except Exception as e:
            print(f"Error generating execution plan: {e}")
            import traceback
            traceback.print_exc()
            # Return a basic fallback plan
            return {
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Execute task',
                        'description': task_description,
                        'estimated_duration_seconds': 60,
                        'dependencies': []
                    }
                ],
                'estimated_duration_minutes': 1,
                'requires_approval': True,  # Conservative default
                'approval_reasoning': 'Error during planning, requiring approval for safety',
                'risks': ['Unable to generate detailed plan'],
                'success_criteria': ['Task completed without errors']
            }

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
