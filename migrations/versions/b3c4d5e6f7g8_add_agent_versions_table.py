"""Add agent_versions table for version control

Revision ID: b3c4d5e6f7g8
Revises: a1b2c3d4e5f6
Create Date: 2025-11-17 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7g8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_versions table
    op.create_table('agent_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('is_active_version', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('version_tag', sa.String(length=50), nullable=True),

        # Change tracking
        sa.Column('changed_by_id', sa.Integer(), nullable=False),
        sa.Column('change_summary', sa.String(length=500), nullable=True),
        sa.Column('change_type', sa.String(length=50), nullable=True),
        sa.Column('changes_diff', sa.Text(), nullable=True),

        # Agent configuration snapshot
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(length=255), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),

        # Integration flags
        sa.Column('enable_quickbooks', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('enable_gmail', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('enable_outlook', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('enable_google_drive', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('enable_website_builder', sa.Boolean(), nullable=False, server_default='0'),

        # Timestamp
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint
        sa.UniqueConstraint('agent_id', 'version_number', name='unique_version_per_agent')
    )

    # Create indexes
    op.create_index('ix_agent_versions_agent_id', 'agent_versions', ['agent_id'])
    op.create_index('ix_agent_versions_active', 'agent_versions', ['agent_id', 'is_active_version'])

    # Backfill: Create version 1 for all existing agents
    # This is done with raw SQL to handle the data migration
    op.execute("""
        INSERT INTO agent_versions (
            agent_id,
            version_number,
            is_active_version,
            version_tag,
            changed_by_id,
            change_summary,
            change_type,
            changes_diff,
            name,
            description,
            avatar_url,
            system_prompt,
            model,
            temperature,
            max_tokens,
            enable_quickbooks,
            enable_gmail,
            enable_outlook,
            enable_google_drive,
            enable_website_builder,
            created_at
        )
        SELECT
            a.id,                              -- agent_id
            1,                                 -- version_number (first version)
            TRUE,                              -- is_active_version
            NULL,                              -- version_tag
            a.created_by_id,                   -- changed_by_id
            'Initial version (migrated)',      -- change_summary
            'initial',                         -- change_type
            NULL,                              -- changes_diff
            a.name,
            a.description,
            a.avatar_url,
            a.system_prompt,
            a.model,
            a.temperature,
            a.max_tokens,
            a.enable_quickbooks,
            a.enable_gmail,
            a.enable_outlook,
            a.enable_google_drive,
            a.enable_website_builder,
            a.created_at
        FROM agents a
    """)


def downgrade():
    # Drop indexes
    op.drop_index('ix_agent_versions_active', table_name='agent_versions')
    op.drop_index('ix_agent_versions_agent_id', table_name='agent_versions')

    # Drop table
    op.drop_table('agent_versions')
