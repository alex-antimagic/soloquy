"""backfill_agent_message_recipient_id

Revision ID: c712ca8a9756
Revises: 7e86fc7f44d2, f9a2b8c5d3e1
Create Date: 2026-03-18 00:00:00

Backfills recipient_id on agent response messages (sender_id IS NULL, agent_id IS NOT NULL).
For each agent response, finds the most recent user message to the same agent before it
and uses that user as the recipient.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c712ca8a9756'
down_revision = ('7e86fc7f44d2', 'f9a2b8c5d3e1')
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # For each agent response message with no recipient, find the user who sent the
    # most recent message to this agent before this message was created.
    conn.execute(sa.text("""
        UPDATE messages AS agent_msg
        SET recipient_id = (
            SELECT user_msg.sender_id
            FROM messages AS user_msg
            WHERE user_msg.agent_id = agent_msg.agent_id
              AND user_msg.sender_id IS NOT NULL
              AND user_msg.created_at <= agent_msg.created_at
            ORDER BY user_msg.created_at DESC
            LIMIT 1
        )
        WHERE agent_msg.sender_id IS NULL
          AND agent_msg.agent_id IS NOT NULL
          AND agent_msg.recipient_id IS NULL
    """))


def downgrade():
    # No-op: setting recipient_id back to NULL would break nothing but also lose data
    pass
