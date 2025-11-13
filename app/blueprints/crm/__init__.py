from flask import Blueprint

crm_bp = Blueprint('crm', __name__)

from app.blueprints.crm import routes
