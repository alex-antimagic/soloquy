import os
import secrets
from datetime import timedelta


class Config:
    """Base configuration"""
    # Generate a temporary key for development if not set
    _secret = os.environ.get('SECRET_KEY')
    if not _secret:
        _secret = secrets.token_hex(32)
        print("WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY environment variable for production.")
    SECRET_KEY = _secret

    # Database - Handle Heroku's postgres:// -> postgresql:// conversion
    database_url = os.environ.get('DATABASE_URL') or 'postgresql://localhost/soloquy'
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database Connection Pool Configuration
    # Optimized for production scalability (hundreds of concurrent users)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,           # Number of persistent connections to keep open
        'max_overflow': 40,        # Additional connections allowed above pool_size
        'pool_pre_ping': True,     # Test connection health before using
        'pool_recycle': 300,       # Recycle connections after 5 minutes
        'pool_timeout': 30,        # Timeout for getting connection from pool
    }

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    # Use HTTPS cookies on Heroku (detected by DYNO env var) or when FLASK_ENV is production
    SESSION_COOKIE_SECURE = bool(os.environ.get('DYNO')) or os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # AI
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    # Error Tracking
    SENTRY_DSN = os.environ.get('SENTRY_DSN')

    # Email Configuration (SendGrid)
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@soloquy.app')
    MAIL_ADMIN_EMAIL = os.environ.get('MAIL_ADMIN_EMAIL', 'support@antimagic.com')

    # Cloudinary (File Storage)
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

    # File Upload Settings
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_FILE_EXTENSIONS = {
        # Images
        'png', 'jpg', 'jpeg', 'gif', 'webp',
        # Documents
        'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
        # Spreadsheets
        'csv', 'xls', 'xlsx', 'ods',
        # Presentations
        'ppt', 'pptx', 'odp',
        # Archives
        'zip', 'tar', 'gz',
        # Code
        'py', 'js', 'html', 'css', 'json', 'xml', 'md',
        # Data
        'sql', 'yaml', 'yml'
    }

    # Redis (for SocketIO message queue)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # For rediss:// (SSL) connections, disable strict certificate verification
    # Heroku Redis uses self-signed certificates in chain
    _redis_url = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    if _redis_url.startswith('rediss://'):
        # SSL encryption enabled, but cert chain has self-signed cert
        _redis_url += '?ssl_cert_reqs=none'

    # SocketIO
    SOCKETIO_MESSAGE_QUEUE = _redis_url
    SOCKETIO_ASYNC_MODE = 'eventlet'

    # Application
    TENANTS_PER_PAGE = 20
    MESSAGES_PER_PAGE = 50
    TASKS_PER_PAGE = 25


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    # Add SSL mode for Postgres on Heroku if not already present
    if 'postgresql://' in Config.database_url and 'sslmode' not in Config.database_url:
        SQLALCHEMY_DATABASE_URI = Config.database_url + '?sslmode=require'

    # Note: ANTHROPIC_API_KEY validation happens at runtime, not import time
    # This prevents errors when importing config in development


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    # Use DATABASE_URL from environment if set (for CI), otherwise use local default
    test_db_url = os.environ.get('DATABASE_URL') or 'postgresql://localhost/soloquy_test'
    if test_db_url.startswith('postgres://'):
        test_db_url = test_db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = test_db_url
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False  # Disable rate limiting in tests
    SOCKETIO_ASYNC_MODE = 'threading'  # Use threading mode for tests
    SOCKETIO_MESSAGE_QUEUE = None  # Disable Redis message queue for tests
    LOGIN_DISABLED = True  # Disable Flask-Login authentication checks in tests


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
