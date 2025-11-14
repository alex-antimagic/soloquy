"""add_agent_integration_access

Revision ID: sa0rnh3g96rn
Revises: b17670d41559
Create Date: 2025-11-13 17:04:46

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'sa0rnh3g96rn'
down_revision = 'b17670d41559'
branch_labels = None
depends_on = None


def upgrade():
    # Add integration access control fields to agents table
    # Default to True to maintain current behavior for existing agents
    op.add_column('agents', sa.Column('enable_quickbooks', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    # Remove integration access control fields
    op.drop_column('agents', 'enable_quickbooks')
