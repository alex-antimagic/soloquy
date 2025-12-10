"""Add cross_applet_data_access to agents

Revision ID: 8e50f7e4144c
Revises: baab866886b9
Create Date: 2025-12-10 11:39:56.544206

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e50f7e4144c'
down_revision = 'baab866886b9'
branch_labels = None
depends_on = None


def upgrade():
    # Add enable_cross_applet_data_access column with default True
    # This allows all existing agents to immediately query data from all applets (CRM, HR, Support, Projects)
    op.add_column('agents',
        sa.Column('enable_cross_applet_data_access', sa.Boolean(),
                  nullable=False, server_default='1'))


def downgrade():
    # Remove the cross_applet_data_access column
    op.drop_column('agents', 'enable_cross_applet_data_access')
