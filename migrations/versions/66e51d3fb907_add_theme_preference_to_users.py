"""Add theme_preference to users

Revision ID: 66e51d3fb907
Revises: c5d6e7f8g9h0
Create Date: 2025-11-17 18:47:38.345975

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '66e51d3fb907'
down_revision = 'c5d6e7f8g9h0'
branch_labels = None
depends_on = None


def upgrade():
    # Add theme_preference column with default 'dark'
    op.add_column('users', sa.Column('theme_preference', sa.String(length=10), server_default='dark', nullable=False))


def downgrade():
    # Remove theme_preference column
    op.drop_column('users', 'theme_preference')
