"""add_hybrid_mcp_support

Revision ID: f5b8c9d3a2e1
Revises: a9e4c2b8f3d1
Create Date: 2025-11-14 22:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5b8c9d3a2e1'
down_revision = 'a9e4c2b8f3d1'
branch_labels = None
depends_on = None


def upgrade():
    # Add hybrid tenant/user support to integrations table
    op.add_column('integrations', sa.Column('owner_type', sa.String(length=20), nullable=False, server_default='tenant'))
    op.add_column('integrations', sa.Column('owner_id', sa.Integer(), nullable=True))  # Temporarily nullable
    op.add_column('integrations', sa.Column('display_name', sa.String(length=100), nullable=True))

    # Backfill owner_id with tenant_id for existing integrations (workspace-level by default)
    op.execute("UPDATE integrations SET owner_id = tenant_id WHERE owner_id IS NULL")

    # Make owner_id non-nullable after backfill
    op.alter_column('integrations', 'owner_id', nullable=False)

    # Add MCP-specific fields
    op.add_column('integrations', sa.Column('integration_mode', sa.String(length=20), nullable=True, server_default='oauth'))
    op.add_column('integrations', sa.Column('mcp_server_type', sa.String(length=50), nullable=True))
    op.add_column('integrations', sa.Column('mcp_config_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('mcp_credentials_path', sa.String(length=500), nullable=True))
    op.add_column('integrations', sa.Column('mcp_process_id', sa.Integer(), nullable=True))

    # Drop old unique constraint and create new one
    op.drop_constraint('uq_tenant_integration_type', 'integrations', type_='unique')
    op.create_unique_constraint(
        'uq_tenant_owner_integration_type',
        'integrations',
        ['tenant_id', 'owner_type', 'owner_id', 'integration_type']
    )

    # Add MCP integration access flags to agents table
    op.add_column('agents', sa.Column('enable_gmail', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('agents', sa.Column('enable_outlook', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('agents', sa.Column('enable_google_drive', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove MCP access flags from agents
    op.drop_column('agents', 'enable_google_drive')
    op.drop_column('agents', 'enable_outlook')
    op.drop_column('agents', 'enable_gmail')

    # Restore old unique constraint on integrations
    op.drop_constraint('uq_tenant_owner_integration_type', 'integrations', type_='unique')
    op.create_unique_constraint('uq_tenant_integration_type', 'integrations', ['tenant_id', 'integration_type'])

    # Remove MCP fields from integrations
    op.drop_column('integrations', 'mcp_process_id')
    op.drop_column('integrations', 'mcp_credentials_path')
    op.drop_column('integrations', 'mcp_config_encrypted')
    op.drop_column('integrations', 'mcp_server_type')
    op.drop_column('integrations', 'integration_mode')

    # Remove hybrid support fields
    op.drop_column('integrations', 'display_name')
    op.drop_column('integrations', 'owner_id')
    op.drop_column('integrations', 'owner_type')
