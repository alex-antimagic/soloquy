"""Add plan and billing fields to User model

Revision ID: 5b3ff118ed24
Revises: 4d081dd42652
Create Date: 2025-11-13 12:29:54.425668

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b3ff118ed24'
down_revision = '4d081dd42652'
branch_labels = None
depends_on = None


def upgrade():
    # Add plan and billing columns to users table
    op.add_column('users', sa.Column('plan', sa.String(length=20), nullable=False, server_default='free'))
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True))


def downgrade():
    # Remove plan and billing columns from users table
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'plan')
