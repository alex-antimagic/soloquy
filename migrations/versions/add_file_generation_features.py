"""Add file generation features

Revision ID: add_file_gen_2024
Revises: f6083581ab59
Create Date: 2024-11-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_file_gen_2024'
down_revision = 'f6083581ab59'
branch_labels = None
depends_on = None


def upgrade():
    # Create generated_files table
    op.create_table('generated_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_purpose', sa.String(length=100), nullable=True),
        sa.Column('cloudinary_url', sa.String(length=500), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generated_files_agent_id'), 'generated_files', ['agent_id'], unique=False)
    op.create_index(op.f('ix_generated_files_created_at'), 'generated_files', ['created_at'], unique=False)
    op.create_index(op.f('ix_generated_files_message_id'), 'generated_files', ['message_id'], unique=False)
    op.create_index(op.f('ix_generated_files_tenant_id'), 'generated_files', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_generated_files_user_id'), 'generated_files', ['user_id'], unique=False)

    # Add enable_file_generation column to agents table
    op.add_column('agents', sa.Column('enable_file_generation', sa.Boolean(), nullable=False, server_default='false'))

    # Add enable_file_generation column to agent_versions table
    op.add_column('agent_versions', sa.Column('enable_file_generation', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove enable_file_generation columns
    op.drop_column('agent_versions', 'enable_file_generation')
    op.drop_column('agents', 'enable_file_generation')

    # Drop generated_files table
    op.drop_index(op.f('ix_generated_files_user_id'), table_name='generated_files')
    op.drop_index(op.f('ix_generated_files_tenant_id'), table_name='generated_files')
    op.drop_index(op.f('ix_generated_files_message_id'), table_name='generated_files')
    op.drop_index(op.f('ix_generated_files_created_at'), table_name='generated_files')
    op.drop_index(op.f('ix_generated_files_agent_id'), table_name='generated_files')
    op.drop_table('generated_files')
