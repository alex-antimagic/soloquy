"""
QuickBooks Service
Handles OAuth authentication and API calls to QuickBooks Online
"""
import os
from datetime import datetime, timedelta
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects import Customer, Invoice, CompanyInfo, Preferences, Account
from app.models.integration import Integration
from app import db


class QuickBooksService:
    """Service for interacting with QuickBooks Online API"""

    def __init__(self):
        """Initialize QuickBooks service"""
        # Note: Credentials are now stored per-tenant in the Integration model
        # This class no longer reads from environment variables
        pass

    def get_authorization_url(self, integration):
        """
        Get OAuth authorization URL for QuickBooks

        Args:
            integration: Integration model instance with OAuth credentials

        Returns:
            tuple: (auth_url, state_token)
        """
        if not integration or not integration.client_id or not integration.client_secret:
            raise ValueError("QuickBooks credentials not configured")

        auth_client = AuthClient(
            client_id=integration.client_id,
            client_secret=integration.client_secret,
            environment=integration.environment or 'sandbox',
            redirect_uri=integration.redirect_uri
        )

        scopes = [Scopes.ACCOUNTING]
        auth_url = auth_client.get_authorization_url(scopes)

        return auth_url, auth_client.state_token

    def exchange_code_for_tokens(self, integration, auth_code, realm_id, state_token):
        """
        Exchange authorization code for access and refresh tokens

        Args:
            integration: Integration model instance with OAuth credentials
            auth_code: Authorization code from OAuth callback
            realm_id: Company ID (realm_id) from OAuth callback
            state_token: State token to verify request

        Returns:
            dict: Dictionary with access_token, refresh_token, and company_id
        """
        if not integration or not integration.client_id or not integration.client_secret:
            raise ValueError("QuickBooks credentials not configured")

        auth_client = AuthClient(
            client_id=integration.client_id,
            client_secret=integration.client_secret,
            environment=integration.environment or 'sandbox',
            redirect_uri=integration.redirect_uri,
            state_token=state_token
        )

        auth_client.get_bearer_token(auth_code, realm_id=realm_id)

        return {
            'access_token': auth_client.access_token,
            'refresh_token': auth_client.refresh_token,
            'company_id': realm_id
        }

    def refresh_tokens(self, integration):
        """
        Refresh access token using refresh token

        Args:
            integration: Integration model instance with OAuth credentials and refresh token

        Returns:
            dict: Dictionary with new access_token and refresh_token
        """
        if not integration or not integration.client_id or not integration.client_secret:
            raise ValueError("QuickBooks credentials not configured")

        if not integration.refresh_token:
            raise ValueError("No refresh token available")

        auth_client = AuthClient(
            client_id=integration.client_id,
            client_secret=integration.client_secret,
            environment=integration.environment or 'sandbox',
            redirect_uri=integration.redirect_uri
        )

        auth_client.refresh(refresh_token=integration.refresh_token)

        return {
            'access_token': auth_client.access_token,
            'refresh_token': auth_client.refresh_token
        }

    def get_qb_client(self, integration):
        """
        Get authenticated QuickBooks client

        Args:
            integration: Integration model instance

        Returns:
            QuickBooks: Authenticated QuickBooks client
        """
        if not integration or not integration.client_id or not integration.client_secret:
            raise ValueError("QuickBooks credentials not configured")

        # Check if token needs refresh (tokens expire after 1 hour)
        if integration.last_sync_at and \
           datetime.utcnow() - integration.last_sync_at > timedelta(minutes=50):
            try:
                tokens = self.refresh_tokens(integration)
                integration.update_tokens(tokens['access_token'], tokens['refresh_token'])
                db.session.commit()
            except Exception as e:
                print(f"Error refreshing QuickBooks tokens: {e}")
                raise

        # Create auth client with OAuth credentials
        auth_client = AuthClient(
            client_id=integration.client_id,
            client_secret=integration.client_secret,
            environment=integration.environment or 'sandbox',
            redirect_uri=integration.redirect_uri,
            access_token=integration.access_token,
            refresh_token=integration.refresh_token
        )

        # Create QuickBooks client
        client = QuickBooks(
            auth_client=auth_client,
            refresh_token=integration.refresh_token,
            company_id=integration.company_id,
            minorversion=65  # API minor version
        )

        return client

    # ===== QuickBooks API Methods =====

    def get_company_info(self, integration):
        """
        Get company information

        Args:
            integration: Integration model instance

        Returns:
            dict: Company information
        """
        try:
            client = self.get_qb_client(integration)
            company = CompanyInfo.get(integration.company_id, qb=client)

            return {
                'company_name': company.CompanyName,
                'legal_name': company.LegalName if hasattr(company, 'LegalName') else None,
                'email': company.Email.Address if hasattr(company, 'Email') and company.Email else None,
                'phone': company.PrimaryPhone.FreeFormNumber if hasattr(company, 'PrimaryPhone') and company.PrimaryPhone else None,
                'country': company.Country if hasattr(company, 'Country') else None,
                'fiscal_year_start': company.FiscalYearStartMonth if hasattr(company, 'FiscalYearStartMonth') else None
            }
        except Exception as e:
            print(f"Error fetching company info: {e}")
            return None

    def get_customers(self, integration, limit=100):
        """
        Get list of customers

        Args:
            integration: Integration model instance
            limit: Maximum number of customers to return

        Returns:
            list: List of customer dictionaries
        """
        try:
            client = self.get_qb_client(integration)
            customers = Customer.all(max_results=limit, qb=client)

            return [{
                'id': c.Id,
                'name': c.DisplayName,
                'email': c.PrimaryEmailAddr.Address if hasattr(c, 'PrimaryEmailAddr') and c.PrimaryEmailAddr else None,
                'phone': c.PrimaryPhone.FreeFormNumber if hasattr(c, 'PrimaryPhone') and c.PrimaryPhone else None,
                'balance': float(c.Balance) if hasattr(c, 'Balance') and c.Balance else 0.0,
                'active': c.Active if hasattr(c, 'Active') else True
            } for c in customers]
        except Exception as e:
            print(f"Error fetching customers: {e}")
            return []

    def get_invoices(self, integration, status='all', limit=50):
        """
        Get list of invoices

        Args:
            integration: Integration model instance
            status: Filter by status ('all', 'open', 'overdue', 'paid')
            limit: Maximum number of invoices to return

        Returns:
            list: List of invoice dictionaries
        """
        try:
            client = self.get_qb_client(integration)

            # Build query based on status
            if status == 'open':
                query = f"SELECT * FROM Invoice WHERE Balance > '0' ORDER BY TxnDate DESC MAXRESULTS {limit}"
            elif status == 'overdue':
                today = datetime.utcnow().strftime('%Y-%m-%d')
                query = f"SELECT * FROM Invoice WHERE Balance > '0' AND DueDate < '{today}' ORDER BY DueDate MAXRESULTS {limit}"
            elif status == 'paid':
                query = f"SELECT * FROM Invoice WHERE Balance = '0' ORDER BY TxnDate DESC MAXRESULTS {limit}"
            else:
                query = f"SELECT * FROM Invoice ORDER BY TxnDate DESC MAXRESULTS {limit}"

            invoices = Invoice.query(query, qb=client)

            return [{
                'id': inv.Id,
                'invoice_number': inv.DocNumber if hasattr(inv, 'DocNumber') else None,
                'customer_name': inv.CustomerRef.name if hasattr(inv, 'CustomerRef') and inv.CustomerRef else None,
                'customer_id': inv.CustomerRef.value if hasattr(inv, 'CustomerRef') and inv.CustomerRef else None,
                'total_amount': float(inv.TotalAmt) if hasattr(inv, 'TotalAmt') and inv.TotalAmt else 0.0,
                'balance': float(inv.Balance) if hasattr(inv, 'Balance') and inv.Balance else 0.0,
                'due_date': str(inv.DueDate) if hasattr(inv, 'DueDate') and inv.DueDate else None,
                'txn_date': str(inv.TxnDate) if hasattr(inv, 'TxnDate') and inv.TxnDate else None,
                'status': 'Paid' if (hasattr(inv, 'Balance') and float(inv.Balance) == 0) else 'Open'
            } for inv in invoices]
        except Exception as e:
            print(f"Error fetching invoices: {e}")
            return []

    def get_profit_loss(self, integration, start_date=None, end_date=None):
        """
        Get profit & loss report from QuickBooks

        Args:
            integration: Integration model instance
            start_date: Start date (date object or YYYY-MM-DD string)
            end_date: End date (date object or YYYY-MM-DD string)

        Returns:
            dict: Profit & loss summary with revenue, expenses, and net income
        """
        try:
            # Format dates
            if not start_date:
                start_date = datetime.utcnow().replace(day=1)
            if not end_date:
                end_date = datetime.utcnow()

            # Convert to string if date object
            if hasattr(start_date, 'strftime'):
                start_date_str = start_date.strftime('%Y-%m-%d')
            else:
                start_date_str = start_date

            if hasattr(end_date, 'strftime'):
                end_date_str = end_date.strftime('%Y-%m-%d')
            else:
                end_date_str = end_date

            client = self.get_qb_client(integration)

            # Use QuickBooks Reports API for Profit & Loss
            # Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/report-entities/profitandloss
            report_url = f'/v3/company/{integration.company_id}/reports/ProfitAndLoss'

            # Make request using the client's session
            params = {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'accounting_method': 'Accrual'  # or 'Cash'
            }

            # Use the auth client to make the request
            auth_client = client.auth_client
            response = auth_client.make_request(
                'GET',
                url=report_url,
                params=params,
                header_auth=True
            )

            if response.status_code != 200:
                print(f"QuickBooks API error: {response.status_code} - {response.text}")
                return self._get_fallback_pl_data(start_date_str, end_date_str)

            report_data = response.json()

            # Parse the P&L report
            pl_summary = self._parse_profit_loss_report(report_data)
            pl_summary['start_date'] = start_date_str
            pl_summary['end_date'] = end_date_str

            return pl_summary

        except Exception as e:
            print(f"Error fetching P&L report: {e}")
            # Return fallback data
            return self._get_fallback_pl_data(
                start_date_str if 'start_date_str' in locals() else None,
                end_date_str if 'end_date_str' in locals() else None
            )

    def _parse_profit_loss_report(self, report_data):
        """
        Parse QuickBooks P&L report JSON response

        Args:
            report_data: JSON response from QuickBooks P&L report

        Returns:
            dict: Parsed summary with total_revenue, total_expenses, net_income, gross_profit
        """
        try:
            total_revenue = 0.0
            total_expenses = 0.0
            gross_profit = 0.0
            net_income = 0.0

            # Navigate through the report structure
            rows = report_data.get('Rows', {}).get('Row', [])

            for row in rows:
                row_type = row.get('type', '')
                header = row.get('Header', {})
                group_type = row.get('group', '')

                # Look for Income section
                if 'ColData' in header:
                    col_data = header.get('ColData', [])
                    if col_data and 'value' in col_data[0]:
                        section_name = col_data[0]['value']

                        if 'Total Income' in section_name or 'Total Revenue' in section_name:
                            # Get the total from Summary row
                            summary = row.get('Summary', {})
                            if summary:
                                summary_cols = summary.get('ColData', [])
                                if len(summary_cols) > 1:  # Usually column 1 has the amount
                                    try:
                                        total_revenue = float(summary_cols[1].get('value', 0))
                                    except (ValueError, TypeError):
                                        pass

                        elif 'Total Expenses' in section_name or 'Total Cost' in section_name:
                            summary = row.get('Summary', {})
                            if summary:
                                summary_cols = summary.get('ColData', [])
                                if len(summary_cols) > 1:
                                    try:
                                        total_expenses = float(summary_cols[1].get('value', 0))
                                    except (ValueError, TypeError):
                                        pass

                        elif 'Gross Profit' in section_name:
                            summary = row.get('Summary', {})
                            if summary:
                                summary_cols = summary.get('ColData', [])
                                if len(summary_cols) > 1:
                                    try:
                                        gross_profit = float(summary_cols[1].get('value', 0))
                                    except (ValueError, TypeError):
                                        pass

                        elif 'Net Income' in section_name or 'Net Operating Income' in section_name:
                            summary = row.get('Summary', {})
                            if summary:
                                summary_cols = summary.get('ColData', [])
                                if len(summary_cols) > 1:
                                    try:
                                        net_income = float(summary_cols[1].get('value', 0))
                                    except (ValueError, TypeError):
                                        pass

            # If net_income not found, calculate it
            if net_income == 0 and (total_revenue > 0 or total_expenses > 0):
                net_income = total_revenue - total_expenses

            # If gross_profit not found, use net_income
            if gross_profit == 0 and net_income != 0:
                gross_profit = net_income

            return {
                'total_revenue': total_revenue,
                'total_expenses': total_expenses,
                'net_income': net_income,
                'gross_profit': gross_profit
            }

        except Exception as e:
            print(f"Error parsing P&L report: {e}")
            return {
                'total_revenue': 0.0,
                'total_expenses': 0.0,
                'net_income': 0.0,
                'gross_profit': 0.0
            }

    def _get_fallback_pl_data(self, start_date=None, end_date=None):
        """Return fallback P&L data when API fails"""
        if not start_date:
            start_date = datetime.utcnow().replace(day=1).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')

        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_revenue': 0.0,
            'total_expenses': 0.0,
            'net_income': 0.0,
            'gross_profit': 0.0
        }

    def get_financial_summary(self, integration):
        """
        Get comprehensive financial summary for agent context

        Args:
            integration: Integration model instance

        Returns:
            dict: Financial summary with key metrics
        """
        try:
            company_info = self.get_company_info(integration)
            customers = self.get_customers(integration, limit=10)
            open_invoices = self.get_invoices(integration, status='open', limit=10)
            overdue_invoices = self.get_invoices(integration, status='overdue', limit=10)
            profit_loss = self.get_profit_loss(integration)

            # Calculate totals
            total_ar = sum(c['balance'] for c in customers)
            total_open_invoices = sum(inv['balance'] for inv in open_invoices)
            total_overdue = sum(inv['balance'] for inv in overdue_invoices)

            # Top customers by balance
            top_customers = sorted(customers, key=lambda x: x['balance'], reverse=True)[:5]

            return {
                'company': company_info,
                'metrics': {
                    'total_accounts_receivable': total_ar,
                    'total_open_invoices': total_open_invoices,
                    'total_overdue': total_overdue,
                    'num_open_invoices': len(open_invoices),
                    'num_overdue_invoices': len(overdue_invoices)
                },
                'profit_loss': profit_loss,
                'top_customers': top_customers,
                'overdue_invoices': overdue_invoices
            }
        except Exception as e:
            print(f"Error generating financial summary: {e}")
            return None


# Singleton instance
quickbooks_service = QuickBooksService()
