"""add_token_expires_at_to_integrations

Revision ID: 79326c217553
Revises: c1d81e327972
Create Date: 2025-12-01 09:26:38.769143

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79326c217553'
down_revision = 'c1d81e327972'
branch_labels = None
depends_on = None


def upgrade():
    # Add token_expires_at column to track OAuth token expiry
    op.add_column('integrations', sa.Column('token_expires_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove token_expires_at column
    op.drop_column('integrations', 'token_expires_at')
