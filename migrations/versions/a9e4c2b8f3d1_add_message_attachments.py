"""add_message_attachments

Revision ID: a9e4c2b8f3d1
Revises: 732vlcocjvzt
Create Date: 2025-11-14 20:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9e4c2b8f3d1'
down_revision = '732vlcocjvzt'
branch_labels = None
depends_on = None


def upgrade():
    # Add attachment fields to messages table for image and file uploads
    op.add_column('messages', sa.Column('attachment_url', sa.String(length=500), nullable=True))
    op.add_column('messages', sa.Column('attachment_type', sa.String(length=100), nullable=True))
    op.add_column('messages', sa.Column('attachment_filename', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('attachment_size', sa.Integer(), nullable=True))


def downgrade():
    # Remove attachment fields
    op.drop_column('messages', 'attachment_size')
    op.drop_column('messages', 'attachment_filename')
    op.drop_column('messages', 'attachment_type')
    op.drop_column('messages', 'attachment_url')
