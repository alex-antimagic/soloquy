"""Add azure_tenant_id to integrations

Revision ID: f2924eddc4db
Revises: 67b82a672607
Create Date: 2025-12-03 10:56:55.806791

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2924eddc4db'
down_revision = '67b82a672607'
branch_labels = None
depends_on = None


def upgrade():
    # Add azure_tenant_id column for storing Azure AD tenant identifier
    op.add_column('integrations', sa.Column('azure_tenant_id', sa.String(length=255), nullable=True))


def downgrade():
    # Remove azure_tenant_id column
    op.drop_column('integrations', 'azure_tenant_id')
