# Soloquy - Multi-Tenant Business Management Platform

A Slack-inspired, multi-tenant Flask application for managing businesses with AI-powered department agents.

## Features

- **Multi-Tenant Architecture**: Manage multiple businesses from a single account
- **Department Management**: Organize teams with customizable departments
- **AI Agents**: Claude-powered assistants for each department
- **Real-Time Chat**: Server-Sent Events for live messaging
- **Business Applets**: Tasks, CRM, and Support modules
- **Dark Theme UI**: Slack-inspired interface with Bootstrap 5

## Tech Stack

- **Backend**: Flask (Python 3.9+)
- **Database**: PostgreSQL
- **Frontend**: Jinja2 templates, Bootstrap 5, Vanilla JS
- **AI**: Anthropic Claude API
- **Real-Time**: Server-Sent Events (SSE)

## Installation

### Prerequisites

- Python 3.9 or higher
- PostgreSQL 12 or higher
- pip and virtualenv

### Setup Steps

1. **Clone and navigate to the project**
   ```bash
   cd ~/soloquy
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create PostgreSQL database**
   ```bash
   createdb soloquy
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:
   - `SECRET_KEY`: A secure random string
   - `DATABASE_URL`: Your PostgreSQL connection string (default: `postgresql://localhost/soloquy`)
   - `ANTHROPIC_API_KEY`: Your Anthropic API key for Claude

6. **Initialize database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

7. **Run the application**
   ```bash
   python run.py
   ```

   Or specify a custom port:
   ```bash
   PORT=5000 python run.py
   ```

8. **Access the application**
   Open your browser to `http://localhost:5000`

## Project Structure

```
soloquy/
├── app/
│   ├── __init__.py              # Application factory
│   ├── models/                  # Database models
│   │   ├── user.py             # User model
│   │   ├── tenant.py           # Tenant & membership models
│   │   ├── department.py       # Department model
│   │   ├── agent.py            # AI agent model
│   │   └── message.py          # Message model
│   ├── blueprints/             # Route blueprints
│   │   ├── auth/               # Authentication
│   │   ├── tenant/             # Tenant management
│   │   ├── department/         # Department CRUD
│   │   ├── chat/               # Messaging & AI
│   │   ├── tasks/              # Task management
│   │   ├── crm/                # CRM module
│   │   └── support/            # Support tickets
│   ├── static/                 # CSS, JS, images
│   ├── templates/              # Jinja2 templates
│   └── services/               # Business logic
├── migrations/                 # Database migrations
├── config.py                   # Configuration
├── requirements.txt            # Python dependencies
└── run.py                      # Application entry point
```

## Usage

### First Steps

1. **Register an account** at `/register`
2. **Create a workspace** (tenant) for your business
3. **Create departments** (e.g., Sales, Marketing, Legal)
4. **Add AI agents** to departments with custom instructions
5. **Start chatting** with agents or team members

### Multi-Tenant Features

- Switch between tenants using the dropdown in the sidebar
- Each tenant has isolated data (departments, members, messages)
- Invite users to tenants with different roles (owner, admin, member)

### AI Agents

- Each department can have multiple AI agents
- Agents are powered by Claude and can be customized with:
  - System prompts for specific behavior
  - Model selection (different Claude versions)
  - Temperature settings for response style
  - Max token limits

### Real-Time Features

- Messages appear instantly using Server-Sent Events
- User presence indicators show online/offline status
- Notifications for new messages and mentions

## Development

### Database Migrations

After changing models, create and apply migrations:

```bash
flask db migrate -m "Description of changes"
flask db upgrade
```

### Reset Database

To start fresh:

```bash
dropdb soloquy
createdb soloquy
flask db upgrade
```

### Running Tests

```bash
pytest
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/production) | `development` |
| `SECRET_KEY` | Flask secret key | Random (change in production!) |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://localhost/soloquy` |
| `ANTHROPIC_API_KEY` | Claude API key | None (required for AI features) |
| `PORT` | Server port | `5000` |

## Deployment

For production deployment:

1. Set `FLASK_ENV=production`
2. Use a production-grade WSGI server (gunicorn, uWSGI)
3. Set up proper PostgreSQL instance
4. Configure secure `SECRET_KEY`
5. Enable HTTPS
6. Set up proper logging and monitoring

Example with gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app('production')"
```

## License

Proprietary - All rights reserved

## Support

For issues and questions, please contact the development team.
