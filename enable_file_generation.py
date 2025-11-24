#!/usr/bin/env python3
"""
Enable file generation for all existing agents
"""
from app import create_app, db
from app.models.agent import Agent

app = create_app()

with app.app_context():
    # Get all agents
    agents = Agent.query.all()

    print(f"Found {len(agents)} agents")

    # Enable file generation for all
    updated_count = 0
    for agent in agents:
        if not agent.enable_file_generation:
            agent.enable_file_generation = True
            updated_count += 1
            print(f"  ✓ Enabled file generation for: {agent.name} (ID: {agent.id})")
        else:
            print(f"  - Already enabled for: {agent.name} (ID: {agent.id})")

    # Commit changes
    if updated_count > 0:
        db.session.commit()
        print(f"\n✅ Updated {updated_count} agents successfully!")
    else:
        print(f"\n✅ All agents already have file generation enabled!")
