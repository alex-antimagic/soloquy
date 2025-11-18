import os
from flask import Flask, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_required
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
    storage_uri=os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
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
    from app.blueprints.marketplace import marketplace_bp
    from app.blueprints.pages import pages
    from app.blueprints.website import website_bp, public_bp
    from app.blueprints.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tenant_bp, url_prefix='/tenant')
    app.register_blueprint(department_bp, url_prefix='/department')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(crm_bp, url_prefix='/crm')
    app.register_blueprint(support_bp, url_prefix='/support')
    app.register_blueprint(integrations_bp, url_prefix='/integrations')
    app.register_blueprint(marketplace_bp)  # Agent marketplace at /marketplace
    app.register_blueprint(website_bp)  # Admin routes at /website
    app.register_blueprint(public_bp)  # Public routes at /w/<slug>
    app.register_blueprint(admin_bp)  # System admin at /admin
    app.register_blueprint(pages)

    # Exempt chat blueprint from rate limiting
    limiter.exempt(chat_bp)

    # Register template filters
    from app.utils.message_formatter import format_message_content
    app.jinja_env.filters['format_message'] = format_message_content

    # JSON parsing filter for templates
    import json
    app.jinja_env.filters['from_json'] = lambda x: json.loads(x) if x else []

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

    # API Routes (not under blueprint prefix)
    @app.route('/api/search')
    @login_required
    def api_search():
        """Unified search API across all data types"""
        from flask import request, jsonify, g
        query = request.args.get('q', '').strip()

        if len(query) < 2:
            return jsonify({'results': {}, 'total_count': 0})

        if not g.current_tenant:
            return jsonify({'results': {}, 'total_count': 0, 'error': 'No tenant selected'})

        from app.services.search_service import UnifiedSearchService
        from flask_login import current_user

        try:
            results = UnifiedSearchService.search_all(
                user_id=current_user.id,
                tenant_id=g.current_tenant.id,
                query=query,
                limit=5
            )
            return jsonify(results)
        except Exception as e:
            print(f"Error in unified search: {e}")
            return jsonify({'results': {}, 'total_count': 0, 'error': 'Search failed'}), 500

    return app
