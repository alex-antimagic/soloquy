from flask import Blueprint

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/marketplace')

from app.blueprints.marketplace import routes
