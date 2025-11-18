"""
Admin blueprint for superadmin-only functionality
Includes RQ Dashboard for monitoring background jobs
"""
from flask import Blueprint

# Create admin blueprint
admin_bp = Blueprint(
    'admin',
    __name__,
    template_folder='templates',
    url_prefix='/admin'
)

# Import routes after blueprint creation to avoid circular imports
from . import routes
