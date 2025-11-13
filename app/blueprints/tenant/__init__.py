from flask import Blueprint

tenant_bp = Blueprint('tenant', __name__)

from app.blueprints.tenant import routes
