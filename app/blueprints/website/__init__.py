"""
Website Builder Blueprint
Handles both admin and public website routes
"""
from flask import Blueprint

# Admin blueprint for website management (requires authentication)
website_bp = Blueprint('website', __name__, url_prefix='/website')

# Public blueprint for serving websites (no authentication)
public_bp = Blueprint('public_website', __name__)

# Import routes after blueprint creation to avoid circular imports
from app.blueprints.website import routes, public
