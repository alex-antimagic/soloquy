from flask import Flask, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_socketio import SocketIO
from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
socketio = SocketIO()


def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Initialize Socket.IO with Redis message queue
    socketio.init_app(
        app,
        message_queue=app.config['SOCKETIO_MESSAGE_QUEUE'],
        async_mode=app.config['SOCKETIO_ASYNC_MODE'],
        cors_allowed_origins="*",  # Configure appropriately for production
        logger=True,
        engineio_logger=True
    )

    # Initialize Socket.IO event handlers
    from app.services.socketio_manager import init_socketio_events
    init_socketio_events(socketio)

    # Security headers (Talisman) - only in production
    if config_name == 'production':
        Talisman(
            app,
            force_https=True,
            strict_transport_security=True,
            strict_transport_security_max_age=31536000,  # 1 year
            content_security_policy={
                'default-src': "'self'",
                'script-src': [
                    "'self'",
                    "'unsafe-inline'",  # Needed for Bootstrap inline scripts
                    "https://cdn.jsdelivr.net",
                    "https://cdn.socket.io"  # Needed for Socket.IO client
                ],
                'style-src': [
                    "'self'",
                    "'unsafe-inline'",  # Needed for inline styles
                    "https://cdn.jsdelivr.net"
                ],
                'font-src': [
                    "'self'",
                    "https://cdn.jsdelivr.net"
                ],
                'img-src': [
                    "'self'",
                    "data:",
                    "https:"
                ],
                'connect-src': [
                    "'self'",
                    "https://cdn.jsdelivr.net"  # Allow fetching source maps
                ]
            },
            content_security_policy_nonce_in=[],  # Disable nonce since we're using 'unsafe-inline'
            frame_options='DENY',
            frame_options_allow_from=None,
            content_security_policy_report_only=False
        )

    # Import all models for Flask-Migrate
    with app.app_context():
        from app.models import user, tenant, department, agent, message
        # Initialize MCP credentials on startup
        _initialize_mcp_credentials(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.tenant import tenant_bp
    from app.blueprints.department import department_bp
    from app.blueprints.chat import chat_bp
    from app.blueprints.tasks import tasks_bp
    from app.blueprints.projects import projects_bp
    from app.blueprints.crm import crm_bp
    from app.blueprints.support import support_bp
    from app.blueprints.integrations import integrations_bp
    from app.blueprints.pages import pages

    app.register_blueprint(auth_bp)
    app.register_blueprint(tenant_bp, url_prefix='/tenant')
    app.register_blueprint(department_bp, url_prefix='/department')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(crm_bp, url_prefix='/crm')
    app.register_blueprint(support_bp, url_prefix='/support')
    app.register_blueprint(integrations_bp, url_prefix='/integrations')
    app.register_blueprint(pages)

    # Exempt chat blueprint from rate limiting
    limiter.exempt(chat_bp)

    # Register template filters
    from app.utils.message_formatter import format_message_content
    app.jinja_env.filters['format_message'] = format_message_content

    # Context processor for templates
    @app.context_processor
    def inject_tenant():
        """Make current tenant and enabled applets available to all templates"""
        from app.models.tenant import Tenant
        from app.services.applet_manager import get_enabled_applets

        current_tenant_id = session.get('current_tenant_id')
        current_tenant = None
        enabled_applets = []

        if current_tenant_id:
            current_tenant = Tenant.query.get(current_tenant_id)
            enabled_applets = get_enabled_applets(current_tenant_id)

        return dict(
            current_tenant=current_tenant,
            enabled_applets=enabled_applets
        )

    # Before request handler for tenant context
    @app.before_request
    def load_tenant_context():
        """Load current tenant into g object for easy access"""
        from app.models.tenant import Tenant
        g.current_tenant = None
        current_tenant_id = session.get('current_tenant_id')
        if current_tenant_id:
            g.current_tenant = Tenant.query.get(current_tenant_id)

    # Root route
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('tenant.home'))
        return redirect(url_for('auth.login'))

    return app


def _initialize_mcp_credentials(app):
    """
    Initialize MCP credential files on app startup

    This ensures credential files exist on Heroku's ephemeral filesystem
    before MCP servers start
    """
    import json
    import os
    from pathlib import Path

    try:
        # Only initialize if we're in a web dyno (not during migration or one-off commands)
        if not os.environ.get('DYNO', '').startswith('web'):
            return

        from app.models.integration import Integration

        # Get all MCP-mode integrations
        integrations = Integration.query.filter_by(
            integration_mode='mcp',
            is_active=True
        ).all()

        if not integrations:
            app.logger.info("[MCP INIT] No MCP integrations found")
            return

        # Determine base credentials directory
        if os.path.exists('/app/var/mcp/credentials'):
            base_dir = Path('/app/var/mcp/credentials')
        else:
            base_dir = Path.home() / '.mcp' / 'credentials'
            base_dir.mkdir(parents=True, exist_ok=True)

        # Write credentials for each integration
        for integration in integrations:
            if not all([integration.client_id, integration.client_secret,
                       integration.access_token, integration.refresh_token]):
                app.logger.info(f"[MCP INIT] Skipping integration {integration.id} - missing credentials")
                continue

            # Create integration-specific directory
            creds_dir = base_dir / f'{integration.integration_type}-{integration.owner_type}-{integration.owner_id}'
            creds_dir.mkdir(parents=True, exist_ok=True)

            if integration.mcp_server_type == 'outlook':
                # Write .env file with client credentials
                env_file = creds_dir / '.env'
                with open(env_file, 'w') as f:
                    f.write(f"MS_CLIENT_ID={integration.client_id}\n")
                    f.write(f"MS_CLIENT_SECRET={integration.client_secret}\n")
                env_file.chmod(0o600)

                # Write tokens file
                tokens_file = creds_dir / '.outlook-mcp-tokens.json'
                tokens = {
                    "access_token": integration.access_token,
                    "refresh_token": integration.refresh_token,
                    "expires_at": None
                }
                with open(tokens_file, 'w') as f:
                    json.dump(tokens, f, indent=2)
                tokens_file.chmod(0o600)

                app.logger.info(f"[MCP INIT] Wrote Outlook credentials for {integration.owner_type}-{integration.owner_id}")

    except Exception as e:
        # Don't fail app startup if credential initialization fails
        app.logger.error(f"[MCP INIT] Failed to initialize credentials: {e}")
        import traceback
        app.logger.error(f"[MCP INIT] Traceback: {traceback.format_exc()}")
