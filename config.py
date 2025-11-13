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

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # AI
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    # Cloudinary (File Storage)
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

    # File Upload Settings
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # Redis (for SocketIO message queue)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

    # SocketIO
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
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
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/soloquy_test'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
