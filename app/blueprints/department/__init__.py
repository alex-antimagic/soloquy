from flask import Blueprint

department_bp = Blueprint('department', __name__)

from app.blueprints.department import routes
