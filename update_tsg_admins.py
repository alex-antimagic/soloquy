"""
Update TSG Global workspace to have only Alex and Noah Rafalko as admins.
All other members should be demoted to 'member' role.
"""
import os
import sys

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.tenant import Tenant, TenantMembership
from app.models.user import User

app = create_app()

with app.app_context():
    # Find TSG Global tenant
    tsg_tenant = Tenant.query.filter_by(name='TSG Global').first()

    if not tsg_tenant:
        print("Error: TSG Global tenant not found")
        sys.exit(1)

    print(f"Found TSG Global tenant (ID: {tsg_tenant.id})")

    # Find Alex (assuming the owner)
    owner_membership = TenantMembership.query.filter_by(
        tenant_id=tsg_tenant.id,
        role='owner'
    ).first()

    if not owner_membership:
        print("Error: No owner found for TSG Global")
        sys.exit(1)

    alex_user_id = owner_membership.user_id
    alex_user = User.query.get(alex_user_id)
    print(f"Found owner: {alex_user.full_name} ({alex_user.email})")

    # Find Noah Rafalko by email or name
    noah_user = User.query.filter(
        (User.email.ilike('%noah%')) |
        ((User.first_name.ilike('%Noah%')) & (User.last_name.ilike('%Rafalko%')))
    ).first()

    if not noah_user:
        print("Error: Noah Rafalko not found")
        sys.exit(1)

    print(f"Found Noah: {noah_user.full_name} ({noah_user.email})")

    # Get all TSG Global memberships
    all_memberships = TenantMembership.query.filter_by(tenant_id=tsg_tenant.id).all()

    print(f"\nUpdating {len(all_memberships)} memberships:")

    for membership in all_memberships:
        user = User.query.get(membership.user_id)
        old_role = membership.role

        # Keep owner as owner
        if membership.user_id == alex_user_id:
            new_role = 'owner'
        # Set Noah as admin
        elif membership.user_id == noah_user.id:
            new_role = 'admin'
        # Everyone else becomes member
        else:
            new_role = 'member'

        if old_role != new_role:
            membership.role = new_role
            print(f"  - {user.full_name}: {old_role} → {new_role}")
        else:
            print(f"  - {user.full_name}: {old_role} (no change)")

    # Commit the changes
    db.session.commit()
    print("\n✓ Successfully updated workspace roles")
    print(f"✓ Owner: {alex_user.full_name}")
    print(f"✓ Admin: {noah_user.full_name}")
    print(f"✓ All others: member role")
