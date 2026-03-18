"""add_stripe_usage_item_to_users

Revision ID: d3e4f5g6h7i8
Revises: c712ca8a9756
Create Date: 2026-03-18 00:00:00

Adds stripe_usage_subscription_item_id to users for Stripe metered billing.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd3e4f5g6h7i8'
down_revision = 'c712ca8a9756'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('stripe_usage_subscription_item_id', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('users', 'stripe_usage_subscription_item_id')
