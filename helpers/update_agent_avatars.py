"""
Script to update agent avatars

Usage:
1. For placeholders: python update_agent_avatars.py --placeholders
2. For local files: python update_agent_avatars.py --local

To use real headshots:
1. Download headshots from https://instaheadshots.com/
2. Save them in app/static/images/avatars/ with these names:
   - evan.jpg (male, executive)
   - fiona.jpg (female, finance)
   - maya.jpg (female, marketing)
   - sam.jpg (neutral, sales)
   - sarah.jpg (female, support)
   - parker.jpg (neutral, product)
   - larry.jpg (male, legal)
   - hannah.jpg (female, hr)
   - ian.jpg (male, it)
3. Run: python update_agent_avatars.py --local
"""

import os
import sys
from app import create_app, db
from app.models.agent import Agent

def update_with_placeholders():
    """Update agents with UI Avatars placeholders"""
    app = create_app()
    app.app_context().push()

    # Color scheme for different departments
    avatar_config = {
        'Evan': {'name': 'Evan', 'bg': '4A5568', 'color': 'fff'},  # Executive - dark gray
        'Fiona': {'name': 'Fiona', 'bg': '2D3748', 'color': 'fff'},  # Finance - darker
        'Maya': {'name': 'Maya', 'bg': 'ED64A6', 'color': 'fff'},  # Marketing - pink
        'Sam': {'name': 'Sam', 'bg': '48BB78', 'color': 'fff'},  # Sales - green
        'Sarah': {'name': 'Sarah', 'bg': '4299E1', 'color': 'fff'},  # Support - blue
        'Parker': {'name': 'Parker', 'bg': '9F7AEA', 'color': 'fff'},  # Product - purple
        'Larry': {'name': 'Larry', 'bg': '1A202C', 'color': 'fff'},  # Legal - very dark
        'Hannah': {'name': 'Hannah', 'bg': 'F687B3', 'color': 'fff'},  # HR - light pink
        'Ian': {'name': 'Ian', 'bg': '2C5282', 'color': 'fff'},  # IT - dark blue
    }

    agents = Agent.query.all()
    updated = 0

    for agent in agents:
        if agent.name in avatar_config:
            config = avatar_config[agent.name]
            # UI Avatars API: https://ui-avatars.com/
            avatar_url = f"https://ui-avatars.com/api/?name={config['name']}&background={config['bg']}&color={config['color']}&size=200&bold=true"
            agent.avatar_url = avatar_url
            updated += 1
            print(f"✓ Updated {agent.name} with placeholder avatar")

    db.session.commit()
    print(f"\n✅ Updated {updated} agents with placeholder avatars")
    print("\nTo use real headshots:")
    print("1. Download from https://instaheadshots.com/")
    print("2. Save in app/static/images/avatars/")
    print("3. Run: python update_agent_avatars.py --local")


def update_with_local_files():
    """Update agents with local image files"""
    app = create_app()
    app.app_context().push()

    avatar_files = {
        'Evan': 'evan.jpg',
        'Fiona': 'fiona.jpg',
        'Maya': 'maya.jpg',
        'Sam': 'sam.jpg',
        'Sarah': 'sarah.jpg',
        'Parker': 'parker.jpg',
        'Larry': 'larry.jpg',
        'Hannah': 'hannah.jpg',
        'Ian': 'ian.jpg',
    }

    agents = Agent.query.all()
    updated = 0
    missing = []

    for agent in agents:
        if agent.name in avatar_files:
            filename = avatar_files[agent.name]
            filepath = f"app/static/images/avatars/{filename}"

            if os.path.exists(filepath):
                # Use URL path for web access
                agent.avatar_url = f"/static/images/avatars/{filename}"
                updated += 1
                print(f"✓ Updated {agent.name} with local avatar: {filename}")
            else:
                missing.append(filename)
                print(f"✗ Missing file for {agent.name}: {filename}")

    db.session.commit()
    print(f"\n✅ Updated {updated} agents with local avatars")

    if missing:
        print(f"\n⚠️  Missing {len(missing)} avatar files:")
        for filename in missing:
            print(f"  - {filename}")


def show_current_avatars():
    """Display current avatar configuration"""
    app = create_app()
    app.app_context().push()

    agents = Agent.query.all()
    unique_agents = {}

    # Group by name to avoid duplicates
    for agent in agents:
        if agent.name not in unique_agents:
            unique_agents[agent.name] = agent

    print("Current Avatar Configuration:\n")
    for name, agent in sorted(unique_agents.items()):
        status = "✓ Set" if agent.avatar_url else "✗ Not set"
        print(f"{name:12} {status:12} {agent.avatar_url or ''}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        show_current_avatars()
        sys.exit(0)

    command = sys.argv[1]

    if command == '--placeholders':
        update_with_placeholders()
    elif command == '--local':
        update_with_local_files()
    elif command == '--status':
        show_current_avatars()
    else:
        print(__doc__)
        print("\nUnknown command. Use --placeholders, --local, or --status")
        sys.exit(1)
