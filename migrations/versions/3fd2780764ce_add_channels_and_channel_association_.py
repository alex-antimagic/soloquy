"""Add channels and channel association tables

Revision ID: 3fd2780764ce
Revises: ebc10a0d44b7
Create Date: 2025-11-13 13:14:29.328453

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3fd2780764ce'
down_revision = 'ebc10a0d44b7'
branch_labels = None
depends_on = None


def upgrade():
    # Check if channels table already exists (production database may already have it)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create channels table
    if 'channels' not in existing_tables:
        op.create_table(
        'channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_private', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_archived', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_channels_slug'), 'channels', ['slug'], unique=False)
        op.create_index(op.f('ix_channels_tenant_id'), 'channels', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_channels_department_id'), 'channels', ['department_id'], unique=False)

    # Create channel_members association table
    if 'channel_members' not in existing_tables:
        op.create_table(
            'channel_members',
            sa.Column('channel_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('channel_id', 'user_id')
        )

    # Create channel_agents association table
    if 'channel_agents' not in existing_tables:
        op.create_table(
            'channel_agents',
            sa.Column('channel_id', sa.Integer(), nullable=False),
            sa.Column('agent_id', sa.Integer(), nullable=False),
            sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
            sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
            sa.PrimaryKeyConstraint('channel_id', 'agent_id')
        )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('channel_agents')
    op.drop_table('channel_members')
    op.drop_index(op.f('ix_channels_department_id'), table_name='channels')
    op.drop_index(op.f('ix_channels_tenant_id'), table_name='channels')
    op.drop_index(op.f('ix_channels_slug'), table_name='channels')
    op.drop_table('channels')
