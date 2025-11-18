#!/usr/bin/env python3
"""
Import Enhanced Agents
Applies the enhanced agent configurations from enhanced_agents.json to the database.
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.agent import Agent
from app.models.department import Department
from app.models.task import Task
from app.models.user import User
from app.models.tenant import Tenant


def import_enhanced_agents(json_file='enhanced_agents.json', tenant_id=None, dry_run=False):
    """
    Import enhanced agent configurations from JSON file.

    Args:
        json_file: Path to JSON file with enhanced configurations
        tenant_id: Specific tenant to update (None = all tenants)
        dry_run: If True, show what would be changed without making changes
    """

    # Load enhanced configurations
    print(f"\n{'='*60}")
    print("📥 Importing Enhanced Agent Configurations")
    print(f"{'='*60}\n")

    if not os.path.exists(json_file):
        print(f"❌ Error: File '{json_file}' not found")
        return False

    with open(json_file, 'r') as f:
        data = json.load(f)

    enhanced_agents = data.get('agents', [])
    metadata = data.get('metadata', {})

    print(f"📄 Loaded {len(enhanced_agents)} enhanced agent configurations")
    print(f"📅 Generated: {metadata.get('generated_at', 'Unknown')}")
    print(f"🤖 Model used: {metadata.get('model_used', 'Unknown')}\n")

    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")

    # Get all tenants to update
    if tenant_id:
        tenants = Tenant.query.filter_by(id=tenant_id).all()
        if not tenants:
            print(f"❌ Error: Tenant {tenant_id} not found")
            return False
    else:
        tenants = Tenant.query.all()

    print(f"🏢 Found {len(tenants)} tenant(s) to update\n")

    # Statistics
    stats = {
        'agents_updated': 0,
        'agents_not_found': 0,
        'tasks_created': 0,
        'errors': 0
    }

    # Process each tenant
    for tenant in tenants:
        print(f"{'='*60}")
        print(f"Processing tenant: {tenant.name} (ID: {tenant.id})")
        print(f"{'='*60}\n")

        # Get a system user for this tenant (use first admin/owner or any user)
        system_user = tenant.get_members(role='owner') or tenant.get_members(role='admin')
        if system_user:
            system_user = system_user[0]  # Take first owner/admin
        else:
            all_members = tenant.get_members()
            system_user = all_members[0] if all_members else None

        if not system_user:
            print(f"⚠️  No users found for tenant {tenant.name}, skipping\n")
            continue

        # Process each enhanced agent
        for enhanced in enhanced_agents:
            dept_name = enhanced.get('department')
            agent_name = enhanced.get('name')

            print(f"  Processing {agent_name} ({dept_name})...")

            # Find the department
            department = Department.query.filter_by(
                tenant_id=tenant.id,
                name=dept_name
            ).first()

            if not department:
                print(f"    ⚠️  Department '{dept_name}' not found, skipping")
                stats['agents_not_found'] += 1
                continue

            # Find the agent (primary agent for this department)
            agent = Agent.query.filter_by(
                department_id=department.id,
                is_primary=True
            ).first()

            if not agent:
                print(f"    ⚠️  No primary agent found for {dept_name}, skipping")
                stats['agents_not_found'] += 1
                continue

            # Show changes
            changes = []

            if agent.description != enhanced.get('enhanced_description'):
                changes.append("description")

            if agent.system_prompt != enhanced.get('enhanced_system_prompt'):
                changes.append("system_prompt")

            print(f"    ✅ Found agent: {agent.name}")
            print(f"    📝 Changes to apply: {', '.join(changes) if changes else 'None'}")

            if enhanced.get('research_summary'):
                print(f"    📚 Research: {enhanced['research_summary'][:100]}...")

            # Apply changes
            if not dry_run and changes:
                try:
                    # Update agent
                    agent.description = enhanced.get('enhanced_description', agent.description)
                    agent.system_prompt = enhanced.get('enhanced_system_prompt', agent.system_prompt)

                    # Create version to track changes
                    change_summary = f"Enhanced via AI research: Updated {', '.join(changes)}"
                    agent.create_version(
                        changed_by_user=system_user,
                        change_summary=change_summary,
                        change_type='update'
                    )

                    print(f"    💾 Updated agent and created new version")
                    stats['agents_updated'] += 1

                except Exception as e:
                    print(f"    ❌ Error updating agent: {e}")
                    stats['errors'] += 1
                    continue

            # Create default tasks
            default_tasks = enhanced.get('default_tasks', [])

            if default_tasks:
                print(f"    📋 Creating {len(default_tasks)} default tasks...")

                for task_data in default_tasks:
                    if dry_run:
                        print(f"       - [{task_data.get('priority', 'medium')}] {task_data.get('title')}")
                    else:
                        try:
                            # Calculate due date based on priority
                            priority = task_data.get('priority', 'medium')
                            if priority == 'high':
                                due_date = datetime.utcnow() + timedelta(days=7)
                            elif priority == 'medium':
                                due_date = datetime.utcnow() + timedelta(days=14)
                            else:  # low
                                due_date = datetime.utcnow() + timedelta(days=30)

                            task = Task(
                                title=task_data.get('title')[:200],  # Respect max length
                                description=task_data.get('description'),
                                status='pending',
                                priority=priority,
                                due_date=due_date,
                                tenant_id=tenant.id,
                                department_id=department.id,
                                assigned_to_agent_id=agent.id,
                                created_by_id=system_user.id
                            )

                            db.session.add(task)
                            stats['tasks_created'] += 1

                            print(f"       ✅ [{priority}] {task_data.get('title')}")

                        except Exception as e:
                            print(f"       ❌ Error creating task: {e}")
                            stats['errors'] += 1

                if not dry_run:
                    try:
                        db.session.commit()
                    except Exception as e:
                        print(f"    ❌ Error committing tasks: {e}")
                        db.session.rollback()
                        stats['errors'] += 1

            print()  # Blank line between agents

    # Final summary
    print(f"\n{'='*60}")
    print("📊 Import Summary")
    print(f"{'='*60}\n")
    print(f"✅ Agents updated: {stats['agents_updated']}")
    print(f"📋 Tasks created: {stats['tasks_created']}")
    print(f"⚠️  Agents not found: {stats['agents_not_found']}")
    print(f"❌ Errors: {stats['errors']}")

    if dry_run:
        print(f"\n💡 This was a dry run. Run without --dry-run to apply changes.")
    else:
        print(f"\n✨ Import complete!")

    print()
    return True


def main():
    """Entry point for the import script."""
    import argparse

    parser = argparse.ArgumentParser(description='Import enhanced agent configurations')
    parser.add_argument('--file', default='enhanced_agents.json',
                      help='JSON file with enhanced configurations (default: enhanced_agents.json)')
    parser.add_argument('--tenant', type=int,
                      help='Specific tenant ID to update (default: all tenants)')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be changed without making changes')

    args = parser.parse_args()

    # Create Flask app context
    app = create_app()

    with app.app_context():
        success = import_enhanced_agents(
            json_file=args.file,
            tenant_id=args.tenant,
            dry_run=args.dry_run
        )

        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
