#!/usr/bin/env python3
from app import create_app, db
from app.models.company import Company
from app.models.activity import Activity

app = create_app()

with app.app_context():
    # Count companies and activities before deletion
    company_count = Company.query.count()
    activity_count = Activity.query.count()

    print(f'Found {company_count} companies and {activity_count} activities in the database')
    print()

    if company_count > 0 or activity_count > 0:
        # Delete activities first due to foreign key constraints
        if activity_count > 0:
            print(f'Deleting all {activity_count} activities...')
            Activity.query.delete()
            print(f'Successfully deleted all {activity_count} activities')

        # Then delete companies
        if company_count > 0:
            print(f'Deleting all {company_count} companies...')
            Company.query.delete()
            print(f'Successfully deleted all {company_count} companies')

        db.session.commit()
        print()
        print('Database cleared successfully. You can now re-import the CSV file')
    else:
        print('No companies or activities to delete')
