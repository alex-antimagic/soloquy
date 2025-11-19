"""
Create workspace_applets table for managing enabled/disabled applets per workspace
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Create the workspace_applets table
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workspace_applets (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                applet_key VARCHAR(50) NOT NULL,
                is_enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
                UNIQUE(tenant_id, applet_key)
            )
        """))
        conn.commit()

    print("✓ Created workspace_applets table")

    # Seed all existing tenants with all applets enabled (backward compatibility)
    from app.models.tenant import Tenant

    applets = ['crm', 'projects', 'support', 'tasks', 'chat', 'integrations']
    tenants = Tenant.query.all()

    if tenants:
        print(f"\nSeeding {len(tenants)} existing workspace(s) with all applets enabled...")

        for tenant in tenants:
            for applet_key in applets:
                with db.engine.connect() as conn:
                    # Check if already exists
                    result = conn.execute(text("""
                        SELECT COUNT(*) as count FROM workspace_applets
                        WHERE tenant_id = :tenant_id AND applet_key = :applet_key
                    """), {"tenant_id": tenant.id, "applet_key": applet_key})

                    exists = result.fetchone()[0] > 0

                    if not exists:
                        conn.execute(text("""
                            INSERT INTO workspace_applets (tenant_id, applet_key, is_enabled)
                            VALUES (:tenant_id, :applet_key, TRUE)
                        """), {"tenant_id": tenant.id, "applet_key": applet_key})
                        conn.commit()

            print(f"  ✓ Seeded workspace: {tenant.name} ({tenant.slug})")

        print(f"\n✓ All existing workspaces have been seeded with enabled applets")
    else:
        print("\nNo existing workspaces found - skipping seed")

print("\n✅ Migration completed successfully!")
