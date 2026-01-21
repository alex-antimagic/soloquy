#!/usr/bin/env python3
"""
Backfill Employee Records
Create employee records for existing workspace members.
Run once after deployment of the employee auto-sync feature.

Usage:
    python backfill_employees.py [--tenant-id TENANT_ID]

Options:
    --tenant-id    Optional: Backfill only for a specific tenant
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.services.employee_sync_service import EmployeeSyncService
import argparse


def run_backfill(tenant_id=None):
    """
    Run the employee backfill process.

    Args:
        tenant_id: Optional tenant ID to backfill (if None, backfills all tenants)
    """
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Employee Backfill Script")
        print("=" * 60)

        if tenant_id:
            print(f"Backfilling employees for tenant ID: {tenant_id}")
        else:
            print("Backfilling employees for ALL tenants")

        print("\nStarting backfill process...")

        service = EmployeeSyncService()
        result = service.backfill_existing_users(tenant_id=tenant_id)

        print("\n" + "=" * 60)
        print("BACKFILL COMPLETE")
        print("=" * 60)
        print(f"✓ Created: {result['created']} employee records")
        print(f"⟳ Reactivated: {result['reactivated']} employee records")
        print(f"⊘ Skipped: {result['skipped']} (already exist)")

        if result['errors']:
            print(f"\n⚠ Errors: {len(result['errors'])}")
            for error in result['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(result['errors']) > 10:
                print(f"  ... and {len(result['errors']) - 10} more errors")
        else:
            print(f"✓ No errors")

        print("=" * 60)

        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Backfill employee records for existing workspace members'
    )
    parser.add_argument(
        '--tenant-id',
        type=int,
        help='Optional: Backfill only for a specific tenant ID'
    )

    args = parser.parse_args()

    result = run_backfill(tenant_id=args.tenant_id)

    # Exit with error code if there were any errors
    if result['errors']:
        sys.exit(1)
    else:
        sys.exit(0)
