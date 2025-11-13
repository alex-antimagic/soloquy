"""Add workspace_applets table

Revision ID: ebc10a0d44b7
Revises: 5b3ff118ed24
Create Date: 2025-11-13 12:55:04.742661

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ebc10a0d44b7'
down_revision = '5b3ff118ed24'
branch_labels = None
depends_on = None


def upgrade():
    # Create workspace_applets table
    op.create_table(
        'workspace_applets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('applet_key', sa.String(length=50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'applet_key', name='uq_tenant_applet')
    )


def downgrade():
    # Drop workspace_applets table
    op.drop_table('workspace_applets')
