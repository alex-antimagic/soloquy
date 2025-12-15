"""
Background tasks using RQ (Redis Queue)
Handles long-running operations like competitive analysis
"""
from rq.decorators import job
from redis import Redis
import os


# Redis connection setup
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
if redis_url.startswith('rediss://'):
    redis_url += '?ssl_cert_reqs=none'
redis_conn = Redis.from_url(redis_url)


@job('default', connection=redis_conn, timeout='30m')
def run_competitive_analysis(analysis_id):
    """
    Background job to run competitive analysis

    Args:
        analysis_id: ID of the CompetitiveAnalysis to process

    This job:
    1. Fetches the workspace website and all competitor websites
    2. Calls Claude API for comprehensive analysis
    3. Stores results in the database
    4. Updates status to 'completed' or 'failed'
    """
    from app import create_app, db
    from app.services.competitive_analysis_service import CompetitiveAnalysisService

    app = create_app()

    with app.app_context():
        try:
            print(f"[COMPETITIVE_ANALYSIS] Starting analysis {analysis_id}")
            service = CompetitiveAnalysisService()
            service.run_analysis(analysis_id)
            print(f"[COMPETITIVE_ANALYSIS] Completed analysis {analysis_id}")
            return {"status": "completed", "analysis_id": analysis_id}

        except Exception as e:
            print(f"[COMPETITIVE_ANALYSIS] Error in analysis {analysis_id}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

            # Mark analysis as failed
            from app.models.competitive_analysis import CompetitiveAnalysis
            analysis = CompetitiveAnalysis.query.get(analysis_id)
            if analysis:
                analysis.status = 'failed'
                db.session.commit()

            raise


@job('default', connection=redis_conn, timeout='30m')
def run_similar_lead_discovery(discovery_id):
    """
    Background job to discover similar leads

    Args:
        discovery_id: ID of the SimilarLeadDiscovery to process

    This job:
    1. Analyzes reference company profile
    2. Searches enrichment cache, uses AI, and Google search
    3. Scores and ranks similar companies
    4. Auto-creates Lead records with AI Suggested status
    5. Updates discovery status to completed/failed
    """
    from app import create_app, db
    from app.services.similar_lead_discovery_service import SimilarLeadDiscoveryService

    app = create_app()

    with app.app_context():
        try:
            print(f"[SIMILAR_LEADS] Starting discovery {discovery_id}")
            service = SimilarLeadDiscoveryService()
            service.run_discovery(discovery_id)
            print(f"[SIMILAR_LEADS] Completed discovery {discovery_id}")
            return {"status": "completed", "discovery_id": discovery_id}

        except Exception as e:
            print(f"[SIMILAR_LEADS] Error in discovery {discovery_id}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

            # Mark discovery as failed
            from app.models.similar_lead_discovery import SimilarLeadDiscovery
            discovery = SimilarLeadDiscovery.query.get(discovery_id)
            if discovery:
                discovery.status = 'failed'
                discovery.error_message = str(e)
                db.session.commit()

            raise
