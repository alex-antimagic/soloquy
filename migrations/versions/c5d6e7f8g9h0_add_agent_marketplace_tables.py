"""Add agent marketplace tables

Revision ID: c5d6e7f8g9h0
Revises: b3c4d5e6f7g8
Create Date: 2025-11-17 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'c5d6e7f8g9h0'
down_revision = 'b3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    # Create marketplace_agents table
    op.create_table('marketplace_agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('published_by_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),  # NULL = global/public

        # Agent configuration
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(length=255), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),

        # Categorization
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),  # JSON array

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='0'),

        # Metrics
        sa.Column('install_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_rating', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['published_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),

        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for marketplace_agents
    op.create_index('ix_marketplace_agents_published_by', 'marketplace_agents', ['published_by_id'])
    op.create_index('ix_marketplace_agents_tenant', 'marketplace_agents', ['tenant_id'])
    op.create_index('ix_marketplace_agents_category', 'marketplace_agents', ['category'])
    op.create_index('ix_marketplace_agents_active', 'marketplace_agents', ['is_active'])
    op.create_index('ix_marketplace_agents_featured', 'marketplace_agents', ['is_featured'])

    # Create agent_reviews table
    op.create_table('agent_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('marketplace_agent_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),

        # Review content
        sa.Column('rating', sa.Integer(), nullable=False),  # 1-5
        sa.Column('review_text', sa.Text(), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['marketplace_agent_id'], ['marketplace_agents.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),

        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_reviews
    op.create_index('ix_agent_reviews_marketplace_agent', 'agent_reviews', ['marketplace_agent_id'])
    op.create_index('ix_agent_reviews_user', 'agent_reviews', ['user_id'])
    op.create_index('ix_agent_reviews_tenant', 'agent_reviews', ['tenant_id'])

    # Create agent_installs table
    op.create_table('agent_installs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('marketplace_agent_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),

        # Timestamp
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['marketplace_agent_id'], ['marketplace_agents.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),

        # Primary key
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_installs
    op.create_index('ix_agent_installs_marketplace_agent', 'agent_installs', ['marketplace_agent_id'])
    op.create_index('ix_agent_installs_user', 'agent_installs', ['user_id'])
    op.create_index('ix_agent_installs_tenant', 'agent_installs', ['tenant_id'])


def downgrade():
    # Drop indexes for agent_installs
    op.drop_index('ix_agent_installs_tenant', table_name='agent_installs')
    op.drop_index('ix_agent_installs_user', table_name='agent_installs')
    op.drop_index('ix_agent_installs_marketplace_agent', table_name='agent_installs')

    # Drop indexes for agent_reviews
    op.drop_index('ix_agent_reviews_tenant', table_name='agent_reviews')
    op.drop_index('ix_agent_reviews_user', table_name='agent_reviews')
    op.drop_index('ix_agent_reviews_marketplace_agent', table_name='agent_reviews')

    # Drop indexes for marketplace_agents
    op.drop_index('ix_marketplace_agents_featured', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_active', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_category', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_tenant', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_published_by', table_name='marketplace_agents')

    # Drop tables
    op.drop_table('agent_installs')
    op.drop_table('agent_reviews')
    op.drop_table('marketplace_agents')
