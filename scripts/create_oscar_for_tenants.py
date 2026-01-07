"""
Create Oscar orchestrator agent for all existing tenants
Run this after deploying the orchestrator system migration
"""
import os
import sys

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', '')

from app import create_app, db
from app.models.tenant import Tenant
from app.models.department import Department
from app.models.agent import Agent
from app.models.task import Task
from app.services.default_departments import get_oscar_system_prompt

app = create_app()

def create_oscar():
    """Create Oscar for all existing tenants that don't have one"""
    with app.app_context():
        tenants = Tenant.query.all()
        print(f"Found {len(tenants)} tenants")

        created_count = 0
        skipped_count = 0

        for tenant in tenants:
            # Get Executive department first
            exec_dept = Department.query.filter_by(
                tenant_id=tenant.id,
                slug='executive'
            ).first()

            if not exec_dept:
                print(f"  Warning: No Executive department for tenant '{tenant.name}' - skipping")
                skipped_count += 1
                continue

            # Check if Oscar already exists in this tenant's Executive department
            existing_oscar = Agent.query.filter_by(
                department_id=exec_dept.id,
                name='Oscar',
                agent_type='orchestrator'
            ).first()

            if existing_oscar:
                print(f"  Skipping tenant '{tenant.name}' - Oscar already exists")
                skipped_count += 1
                continue

            # Get tenant owner for task assignment
            owner_membership = tenant.memberships.filter_by(role='owner').first()
            owner_id = owner_membership.user_id if owner_membership else None

            # Create Oscar
            oscar = Agent(
                department_id=exec_dept.id,
                created_by_id=owner_id,
                name='Oscar',
                description='Orchestrator agent that intelligently routes requests to specialist agents',
                system_prompt=get_oscar_system_prompt(),
                avatar_url='/static/images/avatars/oscar.jpg',
                agent_type='orchestrator',
                is_primary=False,
                is_active=True,
                model='claude-sonnet-4-5-20250929',
                enable_cross_applet_data_access=True,
                enable_file_generation=True,
                enable_quickbooks=True
            )
            db.session.add(oscar)
            db.session.flush()  # Get Oscar's ID

            # Create intro task for Oscar
            if owner_id:
                oscar_task = Task(
                    title="Oscar: Introduce Myself to the Team",
                    description="Say hello and explain how I can help orchestrate requests across all departments!",
                    priority='medium',
                    status='pending',
                    tenant_id=tenant.id,
                    department_id=exec_dept.id,
                    assigned_to_agent_id=oscar.id,
                    created_by_id=owner_id
                )
                db.session.add(oscar_task)

            created_count += 1
            print(f"  ✓ Created Oscar for tenant: {tenant.name}")

        # Commit all changes
        if created_count > 0:
            db.session.commit()
            print(f"\n✅ Successfully created Oscar for {created_count} tenant(s)")
        else:
            print(f"\n✅ All tenants already have Oscar")

        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} tenant(s)")

if __name__ == '__main__':
    try:
        create_oscar()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
