"""Check Larry's tool enablement flags"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.agent import Agent

app = create_app(os.getenv('FLASK_ENV', 'production'))

with app.app_context():
    larry = Agent.query.get(25)
    if larry:
        print(f'Agent: {larry.name}')
        print(f'enable_file_generation: {larry.enable_file_generation}')
        print(f'enable_outlook: {larry.enable_outlook}')
        print(f'enable_website_builder: {larry.enable_website_builder}')
    else:
        print('Agent 25 (Larry) not found')
