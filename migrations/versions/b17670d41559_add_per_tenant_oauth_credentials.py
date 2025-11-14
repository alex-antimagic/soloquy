"""add_per_tenant_oauth_credentials

Revision ID: b17670d41559
Revises: eb1411738c80
Create Date: 2025-11-13 16:23:15.350283

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b17670d41559'
down_revision = 'eb1411738c80'
branch_labels = None
depends_on = None


def upgrade():
    # Add per-tenant OAuth app credentials (encrypted)
    op.add_column('integrations', sa.Column('client_id_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('client_secret_encrypted', sa.Text(), nullable=True))
    op.add_column('integrations', sa.Column('redirect_uri', sa.String(length=500), nullable=True))
    op.add_column('integrations', sa.Column('environment', sa.String(length=50), nullable=True))  # 'sandbox' or 'production'


def downgrade():
    # Remove per-tenant OAuth credentials
    op.drop_column('integrations', 'environment')
    op.drop_column('integrations', 'redirect_uri')
    op.drop_column('integrations', 'client_secret_encrypted')
    op.drop_column('integrations', 'client_id_encrypted')
