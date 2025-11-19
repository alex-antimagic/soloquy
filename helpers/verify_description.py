#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company

app = create_app()

with app.app_context():
    # Check a few recently enriched companies
    for company_id in [7, 9, 11, 12, 14, 15, 19]:
        c = Company.query.get(company_id)
        if c:
            print(f'\n{c.name} (ID {c.id}):')
            print(f'  Status: {c.enrichment_status}')
            print(f'  Score: {c.lead_score}')
            print(f'  Description: {c.description}')
            print()
