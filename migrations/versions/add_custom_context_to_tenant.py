"""add_custom_context_to_tenant

Revision ID: c1d2e3f4g5h6
Revises: b5145286969d
Create Date: 2025-11-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4g5h6'
down_revision = 'b5145286969d'
branch_labels = None
depends_on = None


def upgrade():
    # Add custom_context column to tenants table
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('custom_context', sa.Text(), nullable=True))


def downgrade():
    # Remove custom_context column from tenants table
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('custom_context')
