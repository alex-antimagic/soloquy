"""
HR Blueprint
Handles HR/People management routes
"""
from flask import Blueprint

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

from app.blueprints.hr import routes
