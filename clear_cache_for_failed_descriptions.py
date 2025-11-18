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

    # Clear ALL cache entries to force fresh AI analysis for everyone
    print('Clearing ALL enrichment cache entries to force fresh AI analysis...')
    cache_count = CompanyEnrichmentCache.query.count()
    print(f'  Found {cache_count} cache entries')

    CompanyEnrichmentCache.query.delete()
    db.session.commit()

    print()
    print(f'Successfully cleared ALL {cache_count} cache entries')
    print(f'{len(companies)} companies with failed descriptions will get fresh analysis with v171 prompts')
    print('Re-queue these companies to get proper factual descriptions')
