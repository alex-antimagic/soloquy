#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company
from app.services.lead_enrichment_service import enrich_company_background

app = create_app()

with app.app_context():
    # Find all companies with error messages in enrichment_summary
    error_patterns = [
        '%Analysis failed%',
        '%encountered an error%',
        '%Enrichment analysis encountered%'
    ]

    error_companies = set()
    for pattern in error_patterns:
        companies = Company.query.filter(Company.enrichment_summary.like(pattern)).all()
        error_companies.update(companies)

    print(f'Found {len(error_companies)} companies with error messages:')
    print()

    for company in sorted(error_companies, key=lambda c: c.id):
        summary = (company.enrichment_summary[:60] if company.enrichment_summary else 'None')
        print(f'  ID {company.id:3}: {company.name[:30]:30} | score={company.lead_score or 0:3} | {summary}')

    print()
    response = input(f'Re-queue all {len(error_companies)} companies for enrichment? (yes/no): ')

    if response.lower() == 'yes':
        for company in error_companies:
            enrich_company_background.queue(company.id, priority=3)
            print(f'Queued: {company.name}')

        print(f'\nSuccessfully queued {len(error_companies)} companies for re-enrichment')
    else:
        print('Cancelled')
