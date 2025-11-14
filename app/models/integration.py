"""
Integration Model
Stores OAuth credentials and metadata for external integrations
"""
from datetime import datetime
from app import db
from app.utils.encryption import encryption_service


class Integration(db.Model):
    """Model for storing integration credentials and metadata"""
    __tablename__ = 'integrations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    integration_type = db.Column(db.String(50), nullable=False)  # 'quickbooks', 'google_drive'

    # Encrypted credentials
    access_token_encrypted = db.Column(db.Text)
    refresh_token_encrypted = db.Column(db.Text)
    client_id_encrypted = db.Column(db.Text)
    client_secret_encrypted = db.Column(db.Text)

    # Integration-specific metadata
    company_id = db.Column(db.String(255))  # QuickBooks Realm ID or Google Drive email
    redirect_uri = db.Column(db.String(500))  # Per-tenant OAuth redirect URI
    environment = db.Column(db.String(50))  # 'sandbox' or 'production'

    # Timestamps
    connected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_sync_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('integrations', lazy='dynamic'))

    # Unique constraint
    __table_args = (
        db.UniqueConstraint('tenant_id', 'integration_type', name='uq_tenant_integration_type'),
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

    def update_tokens(self, access_token, refresh_token=None):
        """
        Update OAuth tokens

        Args:
            access_token: New access token
            refresh_token: New refresh token (optional)
        """
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        self.last_sync_at = datetime.utcnow()

    def deactivate(self):
        """Deactivate this integration"""
        self.is_active = False
        self.access_token_encrypted = None
        self.refresh_token_encrypted = None
        # Note: We keep client_id and client_secret so tenant can reconnect without re-entering credentials

    def __repr__(self):
        return f'<Integration {self.integration_type} for Tenant {self.tenant_id}>'
