"""
Create channel_agents table for managing agent membership in channels
"""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Create the channel_agents table
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS channel_agents (
                channel_id INTEGER NOT NULL,
                agent_id INTEGER NOT NULL,
                added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (channel_id, agent_id),
                FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        """))
        conn.commit()

    print("✓ Created channel_agents table")
