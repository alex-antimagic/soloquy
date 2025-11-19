"""add message performance indexes

Revision ID: a18fe3d69501d
Revises: f6083581ab59
Create Date: 2025-11-19 11:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a18fe3d69501d'
down_revision = 'f6083581ab59'
branch_labels = None
depends_on = None


def upgrade():
    # Add composite indexes for common query patterns
    # These significantly speed up message queries by conversation type
    op.create_index('idx_messages_channel_created', 'messages', ['channel_id', 'created_at'], unique=False)
    op.create_index('idx_messages_agent_created', 'messages', ['agent_id', 'created_at'], unique=False)
    op.create_index('idx_messages_recipient_created', 'messages', ['recipient_id', 'created_at'], unique=False)
    op.create_index('idx_messages_sender_created', 'messages', ['sender_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('idx_messages_sender_created', table_name='messages')
    op.drop_index('idx_messages_recipient_created', table_name='messages')
    op.drop_index('idx_messages_agent_created', table_name='messages')
    op.drop_index('idx_messages_channel_created', table_name='messages')
