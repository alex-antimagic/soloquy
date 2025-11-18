#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company
from app.models.enrichment_cache import EnrichmentCache

app = create_app()

with app.app_context():
    # Find all companies with "Analysis failed" in description
    companies = Company.query.filter(Company.description.like('%Analysis failed%')).all()

    print(f'Found {len(companies)} companies with "Analysis failed" descriptions')
    print('Clearing their enrichment cache to force fresh AI analysis...')
    print()

    cleared_count = 0
    for company in companies:
        if company.domain:
            # Delete cache entries for this domain
            cache_entries = EnrichmentCache.query.filter_by(domain=company.domain).all()
            for cache in cache_entries:
                db.session.delete(cache)
                cleared_count += 1

            if cache_entries:
                print(f'  Cleared {len(cache_entries)} cache entries for {company.name} ({company.domain})')

    db.session.commit()
    print()
    print(f'Successfully cleared {cleared_count} cache entries for {len(companies)} companies')
    print('Re-queue these companies to get fresh AI analysis with updated descriptions')
