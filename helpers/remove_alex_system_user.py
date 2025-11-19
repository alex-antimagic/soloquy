"""
Remove Alex system user and associated messages from database
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("🧹 Cleaning up Alex system user from database...")
    print("=" * 70)

    # Find Alex user
    with db.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, email, first_name, last_name
            FROM users
            WHERE email = 'alex@soloquy.com'
        """))
        alex_user = result.fetchone()

        if alex_user:
            alex_id = alex_user[0]
            print(f"\n✓ Found Alex user:")
            print(f"   ID: {alex_id}")
            print(f"   Email: {alex_user[1]}")
            print(f"   Name: {alex_user[2]} {alex_user[3]}")

            # Count messages
            result = conn.execute(text("""
                SELECT COUNT(*) FROM messages
                WHERE sender_id = :alex_id OR recipient_id = :alex_id
            """), {"alex_id": alex_id})
            message_count = result.fetchone()[0]
            print(f"\n📨 Messages involving Alex: {message_count}")

            # Delete messages
            if message_count > 0:
                print("\n🗑️  Deleting messages...")
                conn.execute(text("""
                    DELETE FROM messages
                    WHERE sender_id = :alex_id OR recipient_id = :alex_id
                """), {"alex_id": alex_id})
                conn.commit()
                print(f"   ✓ Deleted {message_count} message(s)")

            # Delete user
            print("\n🗑️  Deleting Alex user...")
            conn.execute(text("""
                DELETE FROM users WHERE id = :alex_id
            """), {"alex_id": alex_id})
            conn.commit()
            print("   ✓ Deleted Alex user")

            print("\n" + "=" * 70)
            print("✅ Cleanup completed successfully!")
            print(f"\nSummary:")
            print(f"  - Deleted {message_count} message(s)")
            print(f"  - Deleted 1 user (alex@soloquy.com)")

        else:
            print("\n📝 Alex user not found in database (may have been deleted already)")
            print("✓ Nothing to clean up")

    print("\n" + "=" * 70)
