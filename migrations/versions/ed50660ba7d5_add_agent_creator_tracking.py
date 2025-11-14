"""add_agent_creator_tracking

Revision ID: ed50660ba7d5
Revises: f5b8c9d3a2e1
Create Date: 2025-11-14 10:37:16.192060

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed50660ba7d5'
down_revision = 'f5b8c9d3a2e1'
branch_labels = None
depends_on = None


def upgrade():
    # Add created_by_id column as nullable first
    op.add_column('agents', sa.Column('created_by_id', sa.Integer(), nullable=True))

    # Backfill with workspace owner for existing agents
    # For each agent, find the workspace owner and set as creator
    op.execute("""
        UPDATE agents
        SET created_by_id = (
            SELECT u.id
            FROM users u
            JOIN tenant_memberships tm ON u.id = tm.user_id
            JOIN departments d ON d.tenant_id = tm.tenant_id
            WHERE d.id = agents.department_id
              AND tm.role = 'owner'
            LIMIT 1
        )
    """)

    # Make the column NOT NULL after backfilling
    op.alter_column('agents', 'created_by_id', nullable=False)

    # Add index for performance
    op.create_index(op.f('ix_agents_created_by_id'), 'agents', ['created_by_id'], unique=False)

    # Add foreign key constraint
    op.create_foreign_key('fk_agents_created_by_user', 'agents', 'users', ['created_by_id'], ['id'])


def downgrade():
    # Drop foreign key constraint
    op.drop_constraint('fk_agents_created_by_user', 'agents', type_='foreignkey')

    # Drop index
    op.drop_index(op.f('ix_agents_created_by_id'), table_name='agents')

    # Drop column
    op.drop_column('agents', 'created_by_id')
