#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company

app = create_app()

with app.app_context():
    # Check Listen Up Espanola and Creacomm
    for name_part in ['Listen Up', 'Creacomm']:
        c = Company.query.filter(Company.name.like(f'%{name_part}%')).first()
        if c:
            print(f'\n{c.name} (ID {c.id}):')
            print(f'  Status: {c.enrichment_status}')
            print(f'  Score: {c.lead_score}')
            print(f'  Description: {c.description[:200] if c.description else "None"}')
            print(f'  Summary: {c.enrichment_summary[:150] if c.enrichment_summary else "None"}...')
