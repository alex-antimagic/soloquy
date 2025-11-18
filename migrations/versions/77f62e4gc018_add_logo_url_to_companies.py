"""Add logo_url to companies

Revision ID: 77f62e4gc018
Revises: 66e51d3fb907
Create Date: 2025-11-18 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77f62e4gc018'
down_revision = '66e51d3fb907'
branch_labels = None
depends_on = None


def upgrade():
    # Add logo_url column to companies table
    op.add_column('companies', sa.Column('logo_url', sa.String(length=500), nullable=True))


def downgrade():
    # Remove logo_url column from companies table
    op.drop_column('companies', 'logo_url')
