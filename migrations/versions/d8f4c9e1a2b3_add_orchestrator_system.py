"""Add orchestrator agent system

Revision ID: d8f4c9e1a2b3
Revises:
Create Date: 2026-01-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8f4c9e1a2b3'
down_revision = '2c301830734a'  # Latest migration head
branch_labels = None
depends_on = None


def upgrade():
    # Add agent_type to agents table
    op.add_column('agents', sa.Column('agent_type', sa.String(20), nullable=False, server_default='specialist'))

    # Create agent_user_preferences table
    op.create_table(
        'agent_user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('visible_in_sidebar', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('preferred_mode', sa.String(20), nullable=False, server_default='orchestrator'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'agent_id', name='unique_user_agent_pref')
    )

    # Create indexes for agent_user_preferences
    op.create_index('ix_agent_user_preferences_user_id', 'agent_user_preferences', ['user_id'])
    op.create_index('ix_agent_user_preferences_agent_id', 'agent_user_preferences', ['agent_id'])

    # Create agent_delegations table
    op.create_table(
        'agent_delegations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('orchestrator_id', sa.Integer(), nullable=False),
        sa.Column('specialist_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('user_query', sa.Text(), nullable=True),
        sa.Column('delegation_reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['orchestrator_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['specialist_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_delegations
    op.create_index('ix_agent_delegations_orchestrator_id', 'agent_delegations', ['orchestrator_id'])
    op.create_index('ix_agent_delegations_specialist_id', 'agent_delegations', ['specialist_id'])
    op.create_index('ix_agent_delegations_message_id', 'agent_delegations', ['message_id'])
    op.create_index('ix_agent_delegations_created_at', 'agent_delegations', ['created_at'])


def downgrade():
    # Drop agent_delegations table
    op.drop_index('ix_agent_delegations_created_at', 'agent_delegations')
    op.drop_index('ix_agent_delegations_message_id', 'agent_delegations')
    op.drop_index('ix_agent_delegations_specialist_id', 'agent_delegations')
    op.drop_index('ix_agent_delegations_orchestrator_id', 'agent_delegations')
    op.drop_table('agent_delegations')

    # Drop agent_user_preferences table
    op.drop_index('ix_agent_user_preferences_agent_id', 'agent_user_preferences')
    op.drop_index('ix_agent_user_preferences_user_id', 'agent_user_preferences')
    op.drop_table('agent_user_preferences')

    # Remove agent_type from agents table
    op.drop_column('agents', 'agent_type')
