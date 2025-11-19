"""Add invitations table

Revision ID: f6083581ab59
Revises: 25683b830aa6
Create Date: 2025-11-19 10:46:22.067511

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6083581ab59'
down_revision = '25683b830aa6'
branch_labels = None
depends_on = None


def upgrade():
    # Create invitations table
    op.create_table('invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('invited_by_user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index('idx_invitations_email', 'invitations', ['email'])
    op.create_index('idx_invitations_token', 'invitations', ['token'])


def downgrade():
    # Drop invitations table
    op.drop_index('idx_invitations_token', table_name='invitations')
    op.drop_index('idx_invitations_email', table_name='invitations')
    op.drop_table('invitations')
