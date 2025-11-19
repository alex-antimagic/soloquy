#!/usr/bin/env python3
"""Test QuickBooks configuration detection"""
import os
import sys

# Set up Flask app context
from app import create_app, db
from app.models.integration import Integration

app = create_app()

with app.app_context():
    # Get QuickBooks integration for tenant 2 (antimagic)
    integration = Integration.query.filter_by(
        tenant_id=2,
        integration_type='quickbooks'
    ).first()

    if not integration:
        print("ERROR: No QuickBooks integration found for tenant 2")
        sys.exit(1)

    print(f"Integration ID: {integration.id}")
    print(f"Tenant ID: {integration.tenant_id}")
    print(f"Integration Type: {integration.integration_type}")
    print(f"Is Active: {integration.is_active}")
    print(f"Environment: {integration.environment}")
    print(f"Redirect URI: {integration.redirect_uri}")
    print()
    print(f"Has client_id_encrypted: {integration.client_id_encrypted is not None}")
    print(f"Has client_secret_encrypted: {integration.client_secret_encrypted is not None}")
    print()

    # Test decryption
    try:
        client_id = integration.client_id
        print(f"client_id property value: {client_id}")
        print(f"client_id is None: {client_id is None}")
        print(f"client_id length: {len(client_id) if client_id else 0}")
    except Exception as e:
        print(f"ERROR decrypting client_id: {e}")

    try:
        client_secret = integration.client_secret
        print(f"client_secret property value: {'***REDACTED***' if client_secret else None}")
        print(f"client_secret is None: {client_secret is None}")
        print(f"client_secret length: {len(client_secret) if client_secret else 0}")
    except Exception as e:
        print(f"ERROR decrypting client_secret: {e}")

    print()
    print(f"qb_configured = {bool(integration.client_id and integration.client_secret)}")
