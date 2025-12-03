"""
Integration Model
Stores OAuth credentials and metadata for external integrations
Supports both workspace-level (shared) and user-level (personal) integrations
"""
from datetime import datetime, timedelta
import json
from app import db
from app.utils.encryption import encryption_service


class Integration(db.Model):
    """Model for storing integration credentials and metadata"""
    __tablename__ = 'integrations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    integration_type = db.Column(db.String(50), nullable=False)  # 'quickbooks', 'gmail', 'outlook', 'google_drive'

    # Hybrid support: workspace-level OR user-level
    owner_type = db.Column(db.String(20), nullable=False, default='tenant')  # 'tenant' or 'user'
    owner_id = db.Column(db.Integer, nullable=False)  # tenant_id if owner_type='tenant', user_id if owner_type='user'
    display_name = db.Column(db.String(100))  # e.g., "Sales Team Gmail" or "John's Personal Gmail"

    # Encrypted credentials
    access_token_encrypted = db.Column(db.Text)
    refresh_token_encrypted = db.Column(db.Text)
    client_id_encrypted = db.Column(db.Text)
    client_secret_encrypted = db.Column(db.Text)

    # Integration-specific metadata
    company_id = db.Column(db.String(255))  # QuickBooks Realm ID or Google Drive email
    redirect_uri = db.Column(db.String(500))  # Per-tenant OAuth redirect URI
    environment = db.Column(db.String(50))  # 'sandbox' or 'production'
    azure_tenant_id = db.Column(db.String(255))  # Azure AD tenant ID (GUID or domain like tsgglobal.onmicrosoft.com)

    # MCP-specific fields (Model Context Protocol)
    integration_mode = db.Column(db.String(20), default='oauth')  # 'oauth' or 'mcp'
    mcp_server_type = db.Column(db.String(50))  # 'gmail', 'outlook', 'google_drive' (npm package identifier)
    mcp_config_encrypted = db.Column(db.Text)  # JSON configuration for MCP server (encrypted)
    mcp_credentials_path = db.Column(db.String(500))  # Filesystem path to MCP credentials
    mcp_process_id = db.Column(db.Integer)  # PID of running MCP server process

    # Timestamps
    connected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_sync_at = db.Column(db.DateTime)
    token_expires_at = db.Column(db.DateTime)  # When the access token expires
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('integrations', lazy='dynamic'))

    # Unique constraint: one integration per owner (workspace or user) per type
    __table_args = (
        db.UniqueConstraint('tenant_id', 'owner_type', 'owner_id', 'integration_type',
                          name='uq_tenant_owner_integration_type'),
    )

    @property
    def access_token(self):
        """Decrypt and return access token"""
        if not self.access_token_encrypted:
            return None
        return encryption_service.decrypt(self.access_token_encrypted)

    @access_token.setter
    def access_token(self, value):
        """Encrypt and store access token"""
        if value:
            self.access_token_encrypted = encryption_service.encrypt(value)
        else:
            self.access_token_encrypted = None

    @property
    def refresh_token(self):
        """Decrypt and return refresh token"""
        if not self.refresh_token_encrypted:
            return None
        return encryption_service.decrypt(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value):
        """Encrypt and store refresh token"""
        if value:
            self.refresh_token_encrypted = encryption_service.encrypt(value)
        else:
            self.refresh_token_encrypted = None

    @property
    def client_id(self):
        """Decrypt and return OAuth client ID"""
        if not self.client_id_encrypted:
            return None
        return encryption_service.decrypt(self.client_id_encrypted)

    @client_id.setter
    def client_id(self, value):
        """Encrypt and store OAuth client ID"""
        if value:
            self.client_id_encrypted = encryption_service.encrypt(value)
        else:
            self.client_id_encrypted = None

    @property
    def client_secret(self):
        """Decrypt and return OAuth client secret"""
        if not self.client_secret_encrypted:
            return None
        return encryption_service.decrypt(self.client_secret_encrypted)

    @client_secret.setter
    def client_secret(self, value):
        """Encrypt and store OAuth client secret"""
        if value:
            self.client_secret_encrypted = encryption_service.encrypt(value)
        else:
            self.client_secret_encrypted = None

    @property
    def mcp_config(self):
        """Decrypt and return MCP configuration as dict"""
        if not self.mcp_config_encrypted:
            return None
        decrypted = encryption_service.decrypt(self.mcp_config_encrypted)
        return json.loads(decrypted) if decrypted else None

    @mcp_config.setter
    def mcp_config(self, value):
        """Encrypt and store MCP configuration"""
        if value:
            json_str = json.dumps(value)
            self.mcp_config_encrypted = encryption_service.encrypt(json_str)
        else:
            self.mcp_config_encrypted = None

    def is_workspace_integration(self):
        """Check if this is a workspace-level (shared) integration"""
        return self.owner_type == 'tenant'

    def is_user_integration(self):
        """Check if this is a user-level (personal) integration"""
        return self.owner_type == 'user'

    def needs_refresh(self, buffer_minutes=5):
        """
        Check if access token needs to be refreshed

        Args:
            buffer_minutes: Refresh if token expires within this many minutes (default 5)

        Returns:
            bool: True if token should be refreshed
        """
        if not self.token_expires_at:
            # If we don't have expiry info, check last_sync_at as fallback
            if self.last_sync_at:
                # Assume 1 hour token lifetime, refresh after 55 minutes
                elapsed = (datetime.utcnow() - self.last_sync_at).total_seconds()
                return elapsed > 3300  # 55 minutes
            # No timing info - assume needs refresh
            return True

        # Check if token expires soon
        time_until_expiry = (self.token_expires_at - datetime.utcnow()).total_seconds()
        buffer_seconds = buffer_minutes * 60
        return time_until_expiry <= buffer_seconds

    def get_mcp_process_name(self):
        """Generate unique process name for MCP server"""
        if self.integration_mode != 'mcp':
            return None
        return f"{self.mcp_server_type}-{self.owner_type}-{self.owner_id}"

    def update_tokens(self, access_token, refresh_token=None, expires_in=None):
        """
        Update OAuth tokens

        Args:
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_in: Token lifetime in seconds (optional)
        """
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self.last_sync_at = datetime.utcnow()

    def deactivate(self):
        """Deactivate this integration"""
        self.is_active = False
        self.access_token_encrypted = None
        self.refresh_token_encrypted = None
        # Note: We keep client_id and client_secret so tenant can reconnect without re-entering credentials

    def __repr__(self):
        owner_info = f"{self.owner_type}={self.owner_id}"
        return f'<Integration {self.integration_type} ({owner_info}) for Tenant {self.tenant_id}>'
