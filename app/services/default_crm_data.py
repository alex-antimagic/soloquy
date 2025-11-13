"""
Service for creating default CRM data when a tenant is created
"""
from app import db
from app.models.deal_pipeline import DealPipeline
from app.models.deal_stage import DealStage


def create_default_deal_pipeline(tenant_id):
    """
    Create a default deal pipeline with standard sales stages for a tenant

    Standard stages:
    1. Lead - Initial contact, not yet qualified
    2. Qualified - BANT criteria met
    3. Proposal - Solution proposed
    4. Negotiation - Terms being discussed
    5. Closed Won - Deal won!
    6. Closed Lost - Deal lost

    Args:
        tenant_id: The tenant ID to create the pipeline for
    """
    # Create default pipeline
    pipeline = DealPipeline(
        tenant_id=tenant_id,
        name='Sales Pipeline',
        description='Default sales pipeline for tracking opportunities',
        color='#10B981',  # Green
        icon='💰',
        is_default=True
    )
    db.session.add(pipeline)
    db.session.flush()  # Get pipeline ID

    # Create default stages
    stages = [
        {
            'name': 'Lead',
            'position': 0,
            'color': '#6B7280',  # Gray
            'probability': 10,
            'expected_duration_days': 7
        },
        {
            'name': 'Qualified',
            'position': 1,
            'color': '#3B82F6',  # Blue
            'probability': 25,
            'expected_duration_days': 14
        },
        {
            'name': 'Proposal',
            'position': 2,
            'color': '#8B5CF6',  # Purple
            'probability': 50,
            'expected_duration_days': 14
        },
        {
            'name': 'Negotiation',
            'position': 3,
            'color': '#F59E0B',  # Orange
            'probability': 75,
            'expected_duration_days': 7
        },
        {
            'name': 'Closed Won',
            'position': 4,
            'color': '#10B981',  # Green
            'probability': 100,
            'is_closed_won': True,
            'expected_duration_days': 0
        },
        {
            'name': 'Closed Lost',
            'position': 5,
            'color': '#EF4444',  # Red
            'probability': 0,
            'is_closed_lost': True,
            'expected_duration_days': 0
        }
    ]

    for stage_data in stages:
        stage = DealStage(
            pipeline_id=pipeline.id,
            **stage_data
        )
        db.session.add(stage)

    db.session.commit()

    print(f"✓ Created default deal pipeline with {len(stages)} stages for tenant {tenant_id}")
    return pipeline
