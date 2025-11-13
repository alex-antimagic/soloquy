import os
from dotenv import load_dotenv
from app import create_app, db, socketio

# Load environment variables
load_dotenv()

# Create application
app = create_app(os.getenv('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    """Make database and models available in Flask shell"""
    from app.models.user import User
    from app.models.tenant import Tenant, TenantMembership
    from app.models.department import Department
    from app.models.agent import Agent
    from app.models.message import Message

    return {
        'db': db,
        'User': User,
        'Tenant': Tenant,
        'TenantMembership': TenantMembership,
        'Department': Department,
        'Agent': Agent,
        'Message': Message
    }


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    # Only enable debug mode in development
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    # Use socketio.run() instead of app.run() for WebSocket support
    # Note: use_reloader=False to avoid port conflicts with eventlet
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
