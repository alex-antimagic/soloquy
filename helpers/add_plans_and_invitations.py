"""
Database migration: Add plans and invitations
- Add plan, stripe_customer_id, stripe_subscription_id to users table
- Create invitations table
- Set all existing users to 'free' plan
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("🔧 Database Migration: Plans & Invitations")
    print("=" * 70)

    with db.engine.connect() as conn:
        # Step 1: Add plan columns to users table
        print("\n📋 Step 1: Adding plan fields to users table...")

        try:
            # Add plan column
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS plan VARCHAR(20) DEFAULT 'free' NOT NULL
            """))
            print("   ✓ Added 'plan' column")

            # Add Stripe customer ID column
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)
            """))
            print("   ✓ Added 'stripe_customer_id' column")

            # Add Stripe subscription ID column
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)
            """))
            print("   ✓ Added 'stripe_subscription_id' column")

            conn.commit()
        except Exception as e:
            print(f"   ⚠️  Note: {e}")
            print("   (Columns may already exist)")

        # Step 2: Set all existing users to 'free' plan
        print("\n📋 Step 2: Setting existing users to 'free' plan...")
        result = conn.execute(text("""
            UPDATE users
            SET plan = 'free'
            WHERE plan IS NULL OR plan = ''
        """))
        conn.commit()
        print(f"   ✓ Updated {result.rowcount} user(s) to 'free' plan")

        # Step 3: Create invitations table
        print("\n📋 Step 3: Creating invitations table...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS invitations (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                tenant_id INTEGER NOT NULL,
                invited_by_user_id INTEGER NOT NULL,
                role VARCHAR(20) DEFAULT 'member' NOT NULL,
                token VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
                FOREIGN KEY (invited_by_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """))
        print("   ✓ Created 'invitations' table")

        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_invitations_email
            ON invitations(email)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_invitations_token
            ON invitations(token)
        """))
        print("   ✓ Created indexes on invitations table")

        conn.commit()

        # Step 4: Verify changes
        print("\n📋 Step 4: Verifying migration...")

        # Check users table
        result = conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'users'
            AND column_name IN ('plan', 'stripe_customer_id', 'stripe_subscription_id')
            ORDER BY column_name
        """))
        user_columns = result.fetchall()
        print(f"\n   Users table - New columns:")
        for col in user_columns:
            print(f"     - {col[0]} ({col[1]})")

        # Check invitations table
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'invitations'
            )
        """))
        invitations_exist = result.fetchone()[0]
        print(f"\n   Invitations table: {'✓ Created' if invitations_exist else '✗ Not found'}")

        # Count users by plan
        result = conn.execute(text("""
            SELECT plan, COUNT(*) as count
            FROM users
            GROUP BY plan
            ORDER BY plan
        """))
        print(f"\n   User plans summary:")
        for row in result:
            print(f"     - {row[0]}: {row[1]} user(s)")

    print("\n" + "=" * 70)
    print("✅ Migration completed successfully!")
    print("\nNext steps:")
    print("  1. Restart the Flask application")
    print("  2. Test workspace creation with free plan limits")
    print("  3. Test invitation system")
    print("=" * 70)
