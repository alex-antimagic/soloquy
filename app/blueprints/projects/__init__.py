from flask import Blueprint

projects_bp = Blueprint('projects', __name__)

from app.blueprints.projects import routes
