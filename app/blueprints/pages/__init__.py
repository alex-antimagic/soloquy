from flask import Blueprint

pages = Blueprint('pages', __name__, url_prefix='/pages')

from app.blueprints.pages import routes
