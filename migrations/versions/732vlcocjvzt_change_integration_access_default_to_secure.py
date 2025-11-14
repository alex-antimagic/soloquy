"""change_integration_access_default_to_secure

Revision ID: 732vlcocjvzt
Revises: sa0rnh3g96rn
Create Date: 2025-11-13 17:09:50

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '732vlcocjvzt'
down_revision = 'sa0rnh3g96rn'
branch_labels = None
depends_on = None


def upgrade():
    # Change default to False (secure by default)
    op.alter_column('agents', 'enable_quickbooks',
                    existing_type=sa.Boolean(),
                    server_default='0',
                    existing_nullable=False)

    # Update all existing agents to have integration access disabled by default
    # Admins will need to explicitly enable for agents that need it
    op.execute("UPDATE agents SET enable_quickbooks = false")


def downgrade():
    # Revert to True as default
    op.alter_column('agents', 'enable_quickbooks',
                    existing_type=sa.Boolean(),
                    server_default='1',
                    existing_nullable=False)

    # Revert all agents back to enabled
    op.execute("UPDATE agents SET enable_quickbooks = true")
