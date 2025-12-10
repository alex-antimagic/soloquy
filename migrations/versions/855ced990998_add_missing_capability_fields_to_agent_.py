"""Add missing capability fields to agent_versions

Revision ID: 855ced990998
Revises: 8e50f7e4144c
Create Date: 2025-12-10 11:42:06.912973

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '855ced990998'
down_revision = '8e50f7e4144c'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing capability tracking fields to agent_versions table
    # These were previously missing from version history tracking
    op.add_column('agent_versions',
        sa.Column('enable_competitive_analysis', sa.Boolean(),
                  nullable=False, server_default='0'))
    op.add_column('agent_versions',
        sa.Column('enable_hr_management', sa.Boolean(),
                  nullable=False, server_default='0'))
    op.add_column('agent_versions',
        sa.Column('enable_cross_applet_data_access', sa.Boolean(),
                  nullable=False, server_default='1'))


def downgrade():
    # Remove the added capability fields
    op.drop_column('agent_versions', 'enable_cross_applet_data_access')
    op.drop_column('agent_versions', 'enable_hr_management')
    op.drop_column('agent_versions', 'enable_competitive_analysis')
