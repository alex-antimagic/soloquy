#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company
from redis import Redis
from rq import Queue

app = create_app()

with app.app_context():
    # Find all companies with "Analysis failed" in description field
    companies = Company.query.filter(Company.description.like('%Analysis failed%')).all()

    print(f'Found {len(companies)} companies with "Analysis failed" in description field:')
    print()

    for company in sorted(companies, key=lambda c: c.id):
        desc = (company.description[:60] if company.description else 'None')
        print(f'  ID {company.id:3}: {company.name[:30]:30} | score={company.lead_score or 0:3} | {desc}')

    print()
    response = input(f'Re-queue all {len(companies)} companies for enrichment? (yes/no): ')

    if response.lower() == 'yes':
        # Set up Redis and RQ
        redis_url = app.config['REDIS_URL']
        if redis_url.startswith('rediss://'):
            redis_url += '?ssl_cert_reqs=none'
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('enrichment', connection=redis_conn)

        for company in sorted(companies, key=lambda c: c.id):
            job = queue.enqueue(
                'app.services.lead_enrichment_service.enrich_company_background',
                company.id,
                3,  # priority
                job_timeout='15m'
            )
            print(f'Queued: {company.name} (Job ID: {job.id[:8]}...)')

        print(f'\nSuccessfully queued {len(companies)} companies for re-enrichment')
    else:
        print('Cancelled')
