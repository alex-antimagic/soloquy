#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company

app = create_app()

with app.app_context():
    # Check all completed companies
    companies = Company.query.filter_by(enrichment_status='completed').all()

    print(f'Total completed companies: {len(companies)}')
    print()

    # Check first 10 completed companies
    for c in companies[:10]:
        print(f'{c.name} (ID {c.id}):')
        print(f'  Status: {c.enrichment_status}')
        print(f'  Score: {c.lead_score}')
        desc = c.description[:120] if c.description else 'None'
        print(f'  Description: {desc}...')
        summary = c.enrichment_summary[:120] if c.enrichment_summary else 'None'
        print(f'  Summary: {summary}...')
        print()
