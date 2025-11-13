"""Add read_receipts table

Revision ID: 4d081dd42652
Revises: c1d2e3f4g5h6
Create Date: 2025-11-10 14:31:59.848301

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d081dd42652'
down_revision = 'c1d2e3f4g5h6'
branch_labels = None
depends_on = None


def upgrade():
    # Create read_receipts table
    op.create_table('read_receipts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('message_id', 'user_id', name='unique_message_user_read')
    )
    op.create_index(op.f('ix_read_receipts_message_id'), 'read_receipts', ['message_id'], unique=False)
    op.create_index(op.f('ix_read_receipts_user_id'), 'read_receipts', ['user_id'], unique=False)


def downgrade():
    # Drop read_receipts table
    op.drop_index(op.f('ix_read_receipts_user_id'), table_name='read_receipts')
    op.drop_index(op.f('ix_read_receipts_message_id'), table_name='read_receipts')
    op.drop_table('read_receipts')
