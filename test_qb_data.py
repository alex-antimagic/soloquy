#!/usr/bin/env python3
"""Test QuickBooks data fetching"""
import os
import sys

# Set up Flask app context
from app import create_app, db
from app.models.integration import Integration
from app.services.quickbooks_service import quickbooks_service

app = create_app()

with app.app_context():
    # Get QuickBooks integration for tenant 3 (TSG Global)
    integration = Integration.query.filter_by(
        tenant_id=3,
        integration_type='quickbooks',
        is_active=True
    ).first()

    if not integration:
        print("ERROR: No active QuickBooks integration found for tenant 3")
        sys.exit(1)

    print(f"✅ QuickBooks connected for tenant {integration.tenant_id}")
    print(f"   Company ID: {integration.company_id}")
    print(f"   Connected at: {integration.connected_at}")
    print()

    # Test 1: Get company info
    print("📊 Fetching company information...")
    try:
        company_info = quickbooks_service.get_company_info(integration)
        if company_info:
            print(f"   Company Name: {company_info['company_name']}")
            print(f"   Legal Name: {company_info.get('legal_name', 'N/A')}")
            print(f"   Email: {company_info.get('email', 'N/A')}")
            print(f"   Phone: {company_info.get('phone', 'N/A')}")
            print(f"   Country: {company_info.get('country', 'N/A')}")
        else:
            print("   ❌ Could not fetch company info")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()

    # Test 2: Get customers
    print("👥 Fetching customers (limit 5)...")
    try:
        customers = quickbooks_service.get_customers(integration, limit=5)
        print(f"   Found {len(customers)} customers")
        for customer in customers[:3]:
            print(f"   - {customer['name']}: ${customer['balance']:.2f} balance")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()

    # Test 3: Get invoices
    print("📄 Fetching invoices (limit 5)...")
    try:
        invoices = quickbooks_service.get_invoices(integration, status='all', limit=5)
        print(f"   Found {len(invoices)} invoices")
        for invoice in invoices[:3]:
            print(f"   - Invoice #{invoice.get('invoice_number', 'N/A')}: ${invoice['total_amount']:.2f} ({invoice['status']})")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()

    # Test 4: Get financial summary
    print("💰 Fetching financial summary...")
    try:
        summary = quickbooks_service.get_financial_summary(integration)
        if summary:
            metrics = summary.get('metrics', {})
            print(f"   Total A/R: ${metrics.get('total_accounts_receivable', 0):.2f}")
            print(f"   Open Invoices: ${metrics.get('total_open_invoices', 0):.2f} ({metrics.get('num_open_invoices', 0)} invoices)")
            print(f"   Overdue: ${metrics.get('total_overdue', 0):.2f} ({metrics.get('num_overdue_invoices', 0)} invoices)")
        else:
            print("   ❌ Could not fetch summary")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print()
    print("✅ QuickBooks integration test complete!")
