"""Add integrations table

Revision ID: eb1411738c80
Revises: 3fd2780764ce
Create Date: 2025-11-13 14:07:26.614521

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eb1411738c80'
down_revision = '3fd2780764ce'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('integration_type', sa.String(length=50), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('company_id', sa.String(length=255), nullable=True),
        sa.Column('connected_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'integration_type', name='uq_tenant_integration_type')
    )
    op.create_index(op.f('ix_integrations_tenant_id'), 'integrations', ['tenant_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_integrations_tenant_id'), table_name='integrations')
    op.drop_table('integrations')
