"""
MCP Manager Service
Manages Model Context Protocol server processes and credentials
Supports hybrid workspace-level and user-level integrations
"""
import os
import json
import subprocess
import psutil
import signal
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from flask import current_app
from app import db
from app.models.integration import Integration


class MCPManager:
    """
    Manages MCP (Model Context Protocol) server processes

    Responsibilities:
    - Start/stop MCP server processes
    - Manage credential files with tenant/user isolation
    - Monitor process health
    - Handle process recovery
    - Clean up resources
    """

    def __init__(self):
        """Initialize MCP Manager"""
        self.processes: Dict[str, subprocess.Popen] = {}  # process_name -> Popen object
        self.base_credentials_path = Path(os.getenv('MCP_CREDENTIALS_PATH', '/tmp/mcp/credentials'))
        self._ensure_credentials_directory()

    def _ensure_credentials_directory(self):
        """Create base credentials directory if it doesn't exist"""
        try:
            self.base_credentials_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        except Exception as e:
            current_app.logger.error(f"Failed to create MCP credentials directory: {e}")

    def _get_credentials_path(self, integration: Integration) -> Path:
        """
        Get filesystem path for integration credentials

        Directory structure:
        /var/mcp/credentials/{owner_type}/{owner_id}/{integration_type}/

        Examples:
        - Workspace Gmail: /var/mcp/credentials/tenant/3/gmail/
        - User Gmail: /var/mcp/credentials/user/5/gmail/

        Args:
            integration: Integration model instance

        Returns:
            Path object for credentials directory
        """
        path = self.base_credentials_path / integration.owner_type / str(integration.owner_id) / integration.integration_type
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path

    def _get_process_name(self, integration: Integration) -> str:
        """
        Generate unique process name for MCP server

        Format: {mcp_server_type}-{owner_type}-{owner_id}

        Examples:
        - gmail-tenant-3 (workspace Gmail)
        - gmail-user-5 (John's personal Gmail)
        - outlook-user-8 (Jane's personal Outlook)

        Args:
            integration: Integration model instance

        Returns:
            Unique process name string
        """
        return integration.get_mcp_process_name()

    def write_credentials(self, integration: Integration, credentials: dict) -> str:
        """
        Write OAuth credentials to filesystem for MCP server

        Creates appropriate credential files based on integration type:
        - Gmail: gcp-oauth.keys.json
        - Outlook: .env file with MS_CLIENT_ID and MS_CLIENT_SECRET
        - Google Drive: gcp-oauth.keys.json

        Args:
            integration: Integration model instance
            credentials: Dict containing OAuth credentials

        Returns:
            Path to written credentials file

        Raises:
            IOError: If file write fails
        """
        creds_dir = self._get_credentials_path(integration)

        try:
            if integration.mcp_server_type in ['gmail', 'google_drive']:
                # Google OAuth credentials format
                creds_file = creds_dir / 'gcp-oauth.keys.json'

                oauth_creds = {
                    "installed": {
                        "client_id": credentials.get('client_id'),
                        "client_secret": credentials.get('client_secret'),
                        "redirect_uris": [credentials.get('redirect_uri', 'http://localhost')],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token"
                    }
                }

                with open(creds_file, 'w', mode=0o600) as f:
                    json.dump(oauth_creds, f, indent=2)

                # Also write tokens if available
                if credentials.get('access_token'):
                    tokens_file = creds_dir / '.gdrive-server-credentials.json'
                    tokens = {
                        "type": "authorized_user",
                        "access_token": credentials.get('access_token'),
                        "refresh_token": credentials.get('refresh_token'),
                        "client_id": credentials.get('client_id'),
                        "client_secret": credentials.get('client_secret')
                    }
                    with open(tokens_file, 'w', mode=0o600) as f:
                        json.dump(tokens, f, indent=2)

                current_app.logger.info(f"Wrote Google credentials to {creds_file}")
                return str(creds_file)

            elif integration.mcp_server_type == 'outlook':
                # Microsoft OAuth credentials in .env format
                env_file = creds_dir / '.env'

                with open(env_file, 'w', mode=0o600) as f:
                    f.write(f"MS_CLIENT_ID={credentials.get('client_id')}\n")
                    f.write(f"MS_CLIENT_SECRET={credentials.get('client_secret')}\n")

                # Outlook MCP stores tokens separately
                if credentials.get('access_token'):
                    tokens_file = creds_dir / '.outlook-mcp-tokens.json'
                    tokens = {
                        "access_token": credentials.get('access_token'),
                        "refresh_token": credentials.get('refresh_token'),
                        "expires_at": credentials.get('expires_at')
                    }
                    with open(tokens_file, 'w', mode=0o600) as f:
                        json.dump(tokens, f, indent=2)

                current_app.logger.info(f"Wrote Outlook credentials to {env_file}")
                return str(env_file)

            else:
                raise ValueError(f"Unknown MCP server type: {integration.mcp_server_type}")

        except Exception as e:
            current_app.logger.error(f"Failed to write MCP credentials: {e}")
            raise

    def cleanup_credentials(self, integration: Integration):
        """
        Remove credentials from filesystem

        Args:
            integration: Integration model instance
        """
        creds_dir = self._get_credentials_path(integration)

        try:
            if creds_dir.exists():
                import shutil
                shutil.rmtree(creds_dir)
                current_app.logger.info(f"Cleaned up credentials at {creds_dir}")
        except Exception as e:
            current_app.logger.error(f"Failed to cleanup credentials: {e}")

    def start_mcp_server(self, integration: Integration) -> Tuple[bool, str]:
        """
        Start MCP server process for integration

        Process management:
        - Starts Node.js process running MCP server
        - Sets working directory to credentials path
        - Captures stdout/stderr for logging
        - Stores process ID in integration model

        Args:
            integration: Integration model instance

        Returns:
            Tuple of (success: bool, message: str)
        """
        if integration.integration_mode != 'mcp':
            return False, "Integration is not in MCP mode"

        process_name = self._get_process_name(integration)

        # Check if already running
        if process_name in self.processes and self.is_process_running(process_name):
            return True, f"MCP server {process_name} is already running"

        # Get credentials directory
        creds_dir = self._get_credentials_path(integration)

        # Build command based on MCP server type
        try:
            if integration.mcp_server_type == 'gmail':
                cmd = ['npx', '@gongrzhe/server-gmail-autoauth-mcp']

            elif integration.mcp_server_type == 'outlook':
                cmd = ['npx', 'outlook-mcp']

            elif integration.mcp_server_type == 'google_drive':
                # Using @piotr-agier/google-drive-mcp for full CRUD support
                cmd = ['npx', '@piotr-agier/google-drive-mcp']

            else:
                return False, f"Unknown MCP server type: {integration.mcp_server_type}"

            # Start process
            process = subprocess.Popen(
                cmd,
                cwd=str(creds_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._get_process_env(integration),
                preexec_fn=os.setsid  # Create new process group for clean shutdown
            )

            # Wait briefly to check if process started successfully
            time.sleep(2)

            if process.poll() is not None:
                # Process died immediately
                stderr = process.stderr.read().decode('utf-8') if process.stderr else ""
                return False, f"MCP server failed to start: {stderr[:500]}"

            # Store process
            self.processes[process_name] = process

            # Update integration with process ID
            integration.mcp_process_id = process.pid
            integration.mcp_credentials_path = str(creds_dir)
            db.session.commit()

            current_app.logger.info(f"Started MCP server {process_name} with PID {process.pid}")
            return True, f"MCP server started successfully (PID: {process.pid})"

        except Exception as e:
            current_app.logger.error(f"Failed to start MCP server {process_name}: {e}")
            return False, f"Failed to start MCP server: {str(e)}"

    def stop_mcp_server(self, integration: Integration) -> Tuple[bool, str]:
        """
        Stop MCP server process

        Graceful shutdown:
        1. Send SIGTERM (allows cleanup)
        2. Wait up to 5 seconds
        3. Send SIGKILL if still running

        Args:
            integration: Integration model instance

        Returns:
            Tuple of (success: bool, message: str)
        """
        process_name = self._get_process_name(integration)

        if process_name not in self.processes:
            # Try to kill by PID if we have it
            if integration.mcp_process_id:
                return self._kill_by_pid(integration.mcp_process_id)
            return False, f"No process found for {process_name}"

        process = self.processes[process_name]

        try:
            # Send SIGTERM for graceful shutdown
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)

            # Wait up to 5 seconds for graceful shutdown
            for _ in range(50):
                if process.poll() is not None:
                    break
                time.sleep(0.1)

            # Force kill if still running
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=2)

            # Cleanup
            del self.processes[process_name]
            integration.mcp_process_id = None
            db.session.commit()

            current_app.logger.info(f"Stopped MCP server {process_name}")
            return True, f"MCP server stopped successfully"

        except Exception as e:
            current_app.logger.error(f"Failed to stop MCP server {process_name}: {e}")
            return False, f"Failed to stop MCP server: {str(e)}"

    def restart_mcp_server(self, integration: Integration) -> Tuple[bool, str]:
        """
        Restart MCP server process

        Args:
            integration: Integration model instance

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Stop first
        self.stop_mcp_server(integration)

        # Brief pause
        time.sleep(1)

        # Start again
        return self.start_mcp_server(integration)

    def is_process_running(self, process_name: str) -> bool:
        """
        Check if MCP server process is running

        Args:
            process_name: Unique process identifier

        Returns:
            True if process is alive, False otherwise
        """
        if process_name not in self.processes:
            return False

        process = self.processes[process_name]
        return process.poll() is None

    def get_process_status(self, integration: Integration) -> Dict:
        """
        Get detailed status of MCP server process

        Args:
            integration: Integration model instance

        Returns:
            Dict with status information
        """
        process_name = self._get_process_name(integration)

        status = {
            'process_name': process_name,
            'running': False,
            'pid': integration.mcp_process_id,
            'cpu_percent': None,
            'memory_mb': None,
            'uptime_seconds': None
        }

        if process_name in self.processes and self.is_process_running(process_name):
            process = self.processes[process_name]
            status['running'] = True

            try:
                ps_process = psutil.Process(process.pid)
                status['cpu_percent'] = ps_process.cpu_percent(interval=0.1)
                status['memory_mb'] = ps_process.memory_info().rss / (1024 * 1024)
                status['uptime_seconds'] = time.time() - ps_process.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return status

    def cleanup_all(self):
        """
        Stop all MCP server processes

        Called on application shutdown
        """
        current_app.logger.info("Stopping all MCP servers...")

        for process_name, process in list(self.processes.items()):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
            except Exception as e:
                current_app.logger.error(f"Error stopping {process_name}: {e}")

        self.processes.clear()
        current_app.logger.info("All MCP servers stopped")

    def _get_process_env(self, integration: Integration) -> dict:
        """
        Build environment variables for MCP server process

        Args:
            integration: Integration model instance

        Returns:
            Dict of environment variables
        """
        env = os.environ.copy()

        # Add any MCP-specific env vars from config
        if integration.mcp_config:
            for key, value in integration.mcp_config.items():
                env[key] = str(value)

        return env

    def _kill_by_pid(self, pid: int) -> Tuple[bool, str]:
        """
        Kill process by PID

        Args:
            pid: Process ID

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            psutil.Process(pid).terminate()
            return True, f"Terminated process {pid}"
        except psutil.NoSuchProcess:
            return False, f"Process {pid} not found"
        except psutil.AccessDenied:
            return False, f"Access denied to process {pid}"
        except Exception as e:
            return False, f"Error terminating process {pid}: {str(e)}"


# Global MCP manager instance
mcp_manager = MCPManager()
