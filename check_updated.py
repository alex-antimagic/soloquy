#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company

app = create_app()

with app.app_context():
    # Check the companies that just finished
    company_ids = [25, 27, 36]  # Network Intelligence, Launch Labs, Textback.ai

    for cid in company_ids:
        c = Company.query.filter_by(id=cid).first()
        if c:
            print(f'{c.name} (ID {c.id}):')
            print(f'  Score: {c.lead_score}')
            summary = c.enrichment_summary[:150] if c.enrichment_summary else 'None'
            print(f'  Summary: {summary}...')
            print()
