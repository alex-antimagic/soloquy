#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company
from redis import Redis
from rq import Queue

app = create_app()

with app.app_context():
    # Find all companies that aren't completed
    all_companies = Company.query.all()
    to_enrich = [c for c in all_companies if c.enrichment_status != 'completed']

    print(f'Total companies: {len(all_companies)}')
    print(f'Completed: {len([c for c in all_companies if c.enrichment_status == "completed"])}')
    print(f'To enrich: {len(to_enrich)}')
    print()

    if to_enrich:
        # Set up Redis and RQ
        redis_url = app.config['REDIS_URL']
        if redis_url.startswith('rediss://'):
            redis_url += '?ssl_cert_reqs=none'
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('enrichment', connection=redis_conn)

        print(f'Queuing {len(to_enrich)} companies for enrichment...')
        print()

        for company in sorted(to_enrich, key=lambda c: c.id):
            job = queue.enqueue(
                'app.services.lead_enrichment_service.enrich_company_background',
                company.id,
                3,  # priority
                job_timeout='15m'
            )
            print(f'Queued: {company.name[:40]:40} (ID {company.id:3}, Job: {job.id[:8]}...)')

        print()
        print(f'Successfully queued {len(to_enrich)} companies for enrichment')
    else:
        print('All companies are already completed')
