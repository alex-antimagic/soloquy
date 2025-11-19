"""
Create channel_members table
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Create the channel_members table
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS channel_members (
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (channel_id, user_id),
                FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """))
        conn.commit()

    print("✓ Created channel_members table")
