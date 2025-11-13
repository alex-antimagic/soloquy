"""
Test script for workspace templates (Business, Family, Custom)
Simulates creating workspaces with each template and verifies correct setup
"""
from app import create_app, db
from app.models.tenant import Tenant, TenantMembership
from app.models.user import User
from app.models.department import Department
from app.services.default_departments import create_default_departments
from app.services.applet_manager import initialize_applets_for_tenant, get_enabled_applets

app = create_app()

def cleanup_test_tenants():
    """Remove any test tenants from previous runs"""
    with app.app_context():
        from app.models.agent import Agent

        test_tenants = Tenant.query.filter(
            Tenant.slug.in_(['test-business', 'test-family', 'test-custom'])
        ).all()
        for tenant in test_tenants:
            # Delete agents first (they reference departments)
            departments = Department.query.filter_by(tenant_id=tenant.id).all()
            for dept in departments:
                Agent.query.filter_by(department_id=dept.id).delete()

            # Now delete departments
            Department.query.filter_by(tenant_id=tenant.id).delete()

            # Delete memberships
            TenantMembership.query.filter_by(tenant_id=tenant.id).delete()

            # Delete workspace applets (cascade should handle this, but be explicit)
            from app.models.workspace_applet import WorkspaceApplet
            WorkspaceApplet.query.filter_by(tenant_id=tenant.id).delete()

            # Delete tenant
            db.session.delete(tenant)
        db.session.commit()
        print(f"✓ Cleaned up {len(test_tenants)} test tenant(s)\n")

def create_test_tenant(name, slug):
    """Helper to create a test tenant"""
    tenant = Tenant(name=name, slug=slug)
    db.session.add(tenant)
    db.session.flush()

    # Add owner (use first user in DB)
    user = User.query.first()
    if user:
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role='owner'
        )
        db.session.add(membership)

    return tenant

def test_business_template():
    """Test Business template: All 9 departments + all 6 applets"""
    print("=" * 70)
    print("TEST 1: BUSINESS TEMPLATE")
    print("=" * 70)

    with app.app_context():
        # Create tenant
        tenant = create_test_tenant("Test Business Workspace", "test-business")

        # Initialize with Business template
        departments = create_default_departments(tenant.id, template='business')
        initialize_applets_for_tenant(tenant.id, applet_keys=None, enabled=True)

        db.session.commit()

        # Verify
        dept_count = Department.query.filter_by(tenant_id=tenant.id).count()
        enabled_applets = get_enabled_applets(tenant.id)

        print(f"\n✓ Created tenant: {tenant.name} (ID: {tenant.id})")
        print(f"\nDepartments created: {dept_count}")
        expected_depts = ['Executive', 'Finance', 'Marketing', 'Sales', 'Support',
                         'Product', 'Legal', 'HR/People', 'IT/Engineering']

        actual_depts = [d.name for d in Department.query.filter_by(tenant_id=tenant.id).all()]
        print(f"Expected: {expected_depts}")
        print(f"Actual:   {actual_depts}")

        print(f"\nApplets enabled: {len(enabled_applets)}")
        print(f"Expected: ['chat', 'crm', 'integrations', 'projects', 'support', 'tasks']")
        print(f"Actual:   {sorted(enabled_applets)}")

        # Assertions
        assert dept_count == 9, f"Expected 9 departments, got {dept_count}"
        assert len(enabled_applets) == 6, f"Expected 6 applets, got {len(enabled_applets)}"
        assert set(enabled_applets) == {'chat', 'crm', 'integrations', 'projects', 'support', 'tasks'}

        print("\n✅ BUSINESS TEMPLATE TEST PASSED!")
        return True

def test_family_template():
    """Test Family template: 1 General department + tasks & chat applets only"""
    print("\n" + "=" * 70)
    print("TEST 2: FAMILY TEMPLATE")
    print("=" * 70)

    with app.app_context():
        # Create tenant
        tenant = create_test_tenant("Test Family Workspace", "test-family")

        # Initialize with Family template
        departments = create_default_departments(tenant.id, template='family')
        initialize_applets_for_tenant(tenant.id, applet_keys=['tasks', 'chat'], enabled=True)

        db.session.commit()

        # Verify
        dept_count = Department.query.filter_by(tenant_id=tenant.id).count()
        enabled_applets = get_enabled_applets(tenant.id)

        print(f"\n✓ Created tenant: {tenant.name} (ID: {tenant.id})")
        print(f"\nDepartments created: {dept_count}")

        dept = Department.query.filter_by(tenant_id=tenant.id).first()
        print(f"Expected: General department with Alex agent")
        print(f"Actual:   {dept.name} department with {dept.agents[0].name if dept.agents else 'no agent'} agent")

        print(f"\nApplets enabled: {len(enabled_applets)}")
        print(f"Expected: ['chat', 'tasks']")
        print(f"Actual:   {sorted(enabled_applets)}")

        # Assertions
        assert dept_count == 1, f"Expected 1 department, got {dept_count}"
        assert dept.name == "General", f"Expected 'General' department, got {dept.name}"
        assert len(enabled_applets) == 2, f"Expected 2 applets, got {len(enabled_applets)}"
        assert set(enabled_applets) == {'chat', 'tasks'}

        print("\n✅ FAMILY TEMPLATE TEST PASSED!")
        return True

def test_custom_template():
    """Test Custom template: Selected departments + selected applets"""
    print("\n" + "=" * 70)
    print("TEST 3: CUSTOM TEMPLATE")
    print("=" * 70)

    with app.app_context():
        # Create tenant
        tenant = create_test_tenant("Test Custom Workspace", "test-custom")

        # Initialize with Custom template (select only 3 departments and 3 applets)
        selected_departments = ['marketing', 'sales', 'support']
        selected_applets = ['crm', 'tasks', 'chat']

        departments = create_default_departments(
            tenant.id,
            template='custom',
            selected_departments=selected_departments
        )
        initialize_applets_for_tenant(
            tenant.id,
            applet_keys=selected_applets,
            enabled=True
        )

        db.session.commit()

        # Verify
        dept_count = Department.query.filter_by(tenant_id=tenant.id).count()
        enabled_applets = get_enabled_applets(tenant.id)

        print(f"\n✓ Created tenant: {tenant.name} (ID: {tenant.id})")
        print(f"\nDepartments created: {dept_count}")

        actual_depts = [d.slug for d in Department.query.filter_by(tenant_id=tenant.id).all()]
        print(f"Expected: {selected_departments}")
        print(f"Actual:   {actual_depts}")

        print(f"\nApplets enabled: {len(enabled_applets)}")
        print(f"Expected: {sorted(selected_applets)}")
        print(f"Actual:   {sorted(enabled_applets)}")

        # Assertions
        assert dept_count == 3, f"Expected 3 departments, got {dept_count}"
        assert set(actual_depts) == set(selected_departments), \
            f"Department mismatch: expected {selected_departments}, got {actual_depts}"
        assert len(enabled_applets) == 3, f"Expected 3 applets, got {len(enabled_applets)}"
        assert set(enabled_applets) == set(selected_applets), \
            f"Applet mismatch: expected {selected_applets}, got {enabled_applets}"

        print("\n✅ CUSTOM TEMPLATE TEST PASSED!")
        return True

def main():
    """Run all template tests"""
    print("\n🧪 WORKSPACE TEMPLATE TESTING")
    print("Testing Business, Family, and Custom templates\n")

    # Run tests
    try:
        test_business_template()
        test_family_template()
        test_custom_template()

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\nAll three workspace templates work correctly:")
        print("  ✓ Business Template: 9 departments + 6 applets")
        print("  ✓ Family Template: 1 department + 2 applets")
        print("  ✓ Custom Template: Selected departments + selected applets")

        print("\n📝 Note: Test workspaces remain in database for inspection.")
        print("   Delete manually via the UI if needed: /tenant/delete/<id>")

        print("\n✅ Testing complete!")
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    main()
