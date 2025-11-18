#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company
from app.models.company_enrichment_cache import CompanyEnrichmentCache

app = create_app()

with app.app_context():
    # Find all companies with "Analysis failed" in description
    companies = Company.query.filter(Company.description.like('%Analysis failed%')).all()

    print(f'Found {len(companies)} companies with "Analysis failed" descriptions')
    print()

    # Instead of deleting cache (foreign key constraint), just NULL out the references
    # This forces fresh AI analysis without breaking foreign key constraints
    print('Clearing cache references for companies with failed descriptions...')

    for company in companies:
        company.enrichment_cache_id = None

    db.session.commit()

    print()
    print(f'Successfully cleared cache references for {len(companies)} companies')
    print('These companies will get fresh AI analysis with v171 prompts on next enrichment')
    print('Re-queue these companies to get proper factual descriptions')
