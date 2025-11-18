"""Add is_superadmin to users

Revision ID: a1b2c3d4e5f6
Revises: f9a2b8c5d3e1
Create Date: 2025-11-18 01:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f9a2b8c5d3e1'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_superadmin column to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='false'))

    # Remove server_default after adding the column (best practice)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_superadmin', server_default=None)


def downgrade():
    # Remove is_superadmin column from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_superadmin')
