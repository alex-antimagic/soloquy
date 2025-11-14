"""
MCP Client for communicating with Model Context Protocol servers
Handles tool discovery and execution via stdio
"""
import json
import subprocess
import asyncio
from typing import Dict, List, Any, Optional
from flask import current_app


class MCPClient:
    """Client for communicating with MCP servers via stdio"""

    def __init__(self, process: subprocess.Popen):
        """
        Initialize MCP client with running process

        Args:
            process: Running MCP server process with stdin/stdout
        """
        self.process = process
        self.request_id = 0

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """
        Send JSON-RPC request to MCP server

        Args:
            method: JSON-RPC method name
            params: Optional parameters dict

        Returns:
            Response from server
        """
        self.request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }

        if params:
            request["params"] = params

        # Send request
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str.encode('utf-8'))
        self.process.stdin.flush()

        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            raise Exception("MCP server closed connection")

        response = json.loads(response_line.decode('utf-8'))

        if "error" in response:
            raise Exception(f"MCP error: {response['error']}")

        return response.get("result", {})

    def initialize(self) -> Dict:
        """
        Initialize MCP connection

        Returns:
            Server capabilities
        """
        return self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {
                    "listChanged": False
                }
            },
            "clientInfo": {
                "name": "soloquy",
                "version": "1.0.0"
            }
        })

    def list_tools(self) -> List[Dict]:
        """
        Get list of available tools from MCP server

        Returns:
            List of tool definitions
        """
        result = self._send_request("tools/list")
        return result.get("tools", [])

    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        Execute a tool on the MCP server

        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments dict

        Returns:
            Tool execution result
        """
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return result

    def close(self):
        """Close connection to MCP server"""
        try:
            if self.process and self.process.poll() is None:
                self.process.stdin.close()
                self.process.stdout.close()
                self.process.wait(timeout=5)
        except:
            pass


def convert_mcp_tools_to_claude(mcp_tools: List[Dict]) -> List[Dict]:
    """
    Convert MCP tool definitions to Claude's tool format

    Args:
        mcp_tools: List of MCP tool definitions

    Returns:
        List of Claude-compatible tool definitions
    """
    claude_tools = []

    for mcp_tool in mcp_tools:
        claude_tool = {
            "name": mcp_tool.get("name", ""),
            "description": mcp_tool.get("description", "")
        }

        # Convert input schema
        if "inputSchema" in mcp_tool:
            claude_tool["input_schema"] = mcp_tool["inputSchema"]

        claude_tools.append(claude_tool)

    return claude_tools


def get_mcp_tools_for_integration(integration) -> Optional[List[Dict]]:
    """
    Get Claude-compatible tool definitions for a running MCP integration

    Args:
        integration: Integration model instance

    Returns:
        List of Claude tool definitions, or None if server not running
    """
    from app.services.mcp_manager import mcp_manager

    try:
        # Check if server is running
        status = mcp_manager.get_process_status(integration)
        if not status.get('running'):
            current_app.logger.warning(f"MCP server not running for integration {integration.id}")
            return None

        pid = status.get('pid')
        if not pid:
            return None

        # Find the process
        import psutil
        try:
            process = psutil.Process(pid)

            # We need to get the actual subprocess.Popen object
            # For now, we'll need to modify MCP manager to expose this
            # As a workaround, we'll start the server was started successfully
            # Let's return a simplified approach for now

            # TODO: Implement proper stdio communication
            # For now, return hardcoded tool definitions based on integration type
            return get_default_tools_for_integration_type(integration.integration_type)

        except psutil.NoSuchProcess:
            return None

    except Exception as e:
        current_app.logger.error(f"Error getting MCP tools: {e}")
        return None


def get_default_tools_for_integration_type(integration_type: str) -> List[Dict]:
    """
    Get default tool definitions for integration types
    This is a temporary solution until we implement full stdio communication

    Args:
        integration_type: Type of integration (outlook, gmail, etc.)

    Returns:
        List of Claude tool definitions
    """
    if integration_type == "outlook":
        return [
            {
                "name": "outlook_list_emails",
                "description": "List emails from Outlook inbox with optional filtering by subject, sender, or date range",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of emails to return (default: 10)",
                            "default": 10
                        },
                        "subject_filter": {
                            "type": "string",
                            "description": "Filter emails by subject containing this text"
                        },
                        "from_filter": {
                            "type": "string",
                            "description": "Filter emails from this sender"
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
                            "description": "Maximum results to return",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "outlook_list_calendar_events",
                "description": "List upcoming calendar events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of events to return",
                            "default": 10
                        },
                        "days_ahead": {
                            "type": "number",
                            "description": "Number of days ahead to look for events",
                            "default": 7
                        }
                    }
                }
            }
        ]

    elif integration_type == "gmail":
        return [
            {
                "name": "gmail_list_emails",
                "description": "List emails from Gmail inbox",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of emails to return",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "gmail_read_email",
                "description": "Read the full content of a specific Gmail email",
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
            }
        ]

    elif integration_type == "google_drive":
        return [
            {
                "name": "drive_list_files",
                "description": "List files in Google Drive",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of files to return",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "drive_read_file",
                "description": "Read the content of a Google Drive file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "The ID of the file to read"
                        }
                    },
                    "required": ["file_id"]
                }
            }
        ]

    return []
