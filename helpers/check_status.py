#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company

app = create_app()

with app.app_context():
    companies = Company.query.all()

    status_counts = {}
    for company in companies:
        status = company.enrichment_status or 'None'
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f'Total: {len(companies)}')
    print(f'\nStatus:')
    for status, count in sorted(status_counts.items()):
        print(f'  {status}: {count}')

    error1 = Company.query.filter(Company.enrichment_summary.like('%Analysis failed%')).count()
    error2 = Company.query.filter(Company.enrichment_summary.like('%encountered an error%')).count()

    print(f'\nError summaries: {error1 + error2}')

    print(f'\nExamples (first 10):')
    for company in companies[:10]:
        status = company.enrichment_status or 'None'
        score = company.lead_score or 0
        summary = (company.enrichment_summary[:40] if company.enrichment_summary else 'None')
        print(f'{company.name[:25]:25} | {status:10} | score={score:3} | {summary}')
