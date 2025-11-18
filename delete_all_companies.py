#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company

app = create_app()

with app.app_context():
    # Count companies before deletion
    company_count = Company.query.count()

    print(f'Found {company_count} companies in the database')
    print()

    if company_count > 0:
        print(f'Deleting all {company_count} companies...')
        Company.query.delete()
        db.session.commit()

        print(f'Successfully deleted all {company_count} companies')
        print('You can now re-import the CSV file')
    else:
        print('No companies to delete')
