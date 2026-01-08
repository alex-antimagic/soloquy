from flask import Blueprint

marketing_bp = Blueprint('marketing', __name__)

from app.blueprints.marketing import routes
