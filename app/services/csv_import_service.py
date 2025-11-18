"""
CSV Import Service for Companies and Contacts
Handles bulk importing from CSV files with validation and error reporting.
"""
import csv
import io
from datetime import datetime
import phonenumbers
from app.models.company import Company
from app.models.contact import Contact
from app import db


def normalize_phone_number(phone_str, default_region='US'):
    """
    Normalize phone number to E.164 format.

    Args:
        phone_str: Phone number string in any format
        default_region: Default country code if not specified (default: US)

    Returns:
        str: Phone number in E.164 format (e.g., +14155552671) or None if invalid
    """
    if not phone_str or not phone_str.strip():
        return None

    try:
        # Parse the phone number
        parsed = phonenumbers.parse(phone_str, default_region)

        # Validate it's a possible number
        if phonenumbers.is_valid_number(parsed):
            # Format to E.164
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        else:
            # If not valid, return None
            return None
    except (phonenumbers.NumberParseException, Exception):
        # If parsing fails, return None
        return None


class CSVImportService:
    """Service for importing companies and contacts from CSV files"""

    @staticmethod
    def import_companies(csv_file, tenant_id, owner_id):
        """
        Import companies from CSV file.

        Args:
            csv_file: File object or string content
            tenant_id: ID of the tenant
            owner_id: ID of the user performing the import

        Returns:
            dict: {
                'success': int,
                'failed': int,
                'total': int,
                'errors': [{'row': int, 'data': dict, 'error': str}],
                'created_ids': [int]
            }
        """
        results = {
            'success': 0,
            'failed': 0,
            'total': 0,
            'errors': [],
            'created_ids': []
        }

        try:
            # Read CSV content
            if hasattr(csv_file, 'read'):
                content = csv_file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8-sig')  # Handles BOM
            else:
                content = csv_file

            # Remove BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]

            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))

            # Normalize headers to lowercase for case-insensitive matching
            normalized_rows = []
            for original_row in csv_reader:
                normalized_row = {k.lower().strip(): v for k, v in original_row.items()}
                normalized_rows.append(normalized_row)

            for row_num, row in enumerate(normalized_rows, start=2):  # Start at 2 (header is row 1)
                results['total'] += 1

                try:
                    # Validate required field
                    name = row.get('name', '').strip()
                    if not name:
                        raise ValueError("Company name is required")

                    # Check for duplicate
                    existing = Company.query.filter_by(
                        tenant_id=tenant_id,
                        name=name
                    ).first()

                    if existing:
                        raise ValueError(f"Company '{name}' already exists")

                    # Normalize phone number to E.164 format
                    phone_raw = row.get('phone', '').strip()
                    phone_normalized = normalize_phone_number(phone_raw) if phone_raw else None

                    # Create company
                    company = Company(
                        tenant_id=tenant_id,
                        name=name,
                        website=row.get('website', '').strip() or None,
                        industry=row.get('industry', '').strip() or None,
                        company_size=row.get('company_size', '').strip() or None,
                        annual_revenue=row.get('annual_revenue', '').strip() or None,
                        address_street=row.get('address_street', '').strip() or None,
                        address_city=row.get('address_city', '').strip() or None,
                        address_state=row.get('address_state', '').strip() or None,
                        address_postal_code=row.get('address_postal_code', '').strip() or None,
                        address_country=row.get('address_country', '').strip() or None,
                        phone=phone_normalized,
                        linkedin_url=row.get('linkedin_url', '').strip() or None,
                        twitter_handle=row.get('twitter_handle', '').strip() or None,
                        description=row.get('description', '').strip() or None,
                        tags=row.get('tags', '').strip() or None,
                        status=row.get('status', 'active').strip() or 'active',
                        lifecycle_stage=row.get('lifecycle_stage', 'lead').strip() or 'lead',
                        owner_id=owner_id
                    )

                    db.session.add(company)
                    db.session.flush()  # Get the ID without committing

                    results['success'] += 1
                    results['created_ids'].append(company.id)

                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'row': row_num,
                        'data': dict(row),
                        'error': str(e)
                    })
                    db.session.rollback()

            # Commit all successful imports
            if results['success'] > 0:
                db.session.commit()

        except Exception as e:
            db.session.rollback()
            results['errors'].append({
                'row': 0,
                'data': {},
                'error': f"CSV parsing error: {str(e)}"
            })
            results['failed'] = results['total']
            results['success'] = 0

        return results

    @staticmethod
    def import_contacts(csv_file, tenant_id, owner_id):
        """
        Import contacts from CSV file.

        Args:
            csv_file: File object or string content
            tenant_id: ID of the tenant
            owner_id: ID of the user performing the import

        Returns:
            dict: {
                'success': int,
                'failed': int,
                'total': int,
                'errors': [{'row': int, 'data': dict, 'error': str}],
                'created_ids': [int]
            }
        """
        results = {
            'success': 0,
            'failed': 0,
            'total': 0,
            'errors': [],
            'created_ids': []
        }

        try:
            # Read CSV content
            if hasattr(csv_file, 'read'):
                content = csv_file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8-sig')  # Handles BOM
            else:
                content = csv_file

            # Remove BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]

            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))

            # Normalize headers to lowercase for case-insensitive matching
            normalized_rows = []
            for original_row in csv_reader:
                normalized_row = {k.lower().strip(): v for k, v in original_row.items()}
                normalized_rows.append(normalized_row)

            for row_num, row in enumerate(normalized_rows, start=2):  # Start at 2 (header is row 1)
                results['total'] += 1

                try:
                    # Validate required fields
                    first_name = row.get('first_name', '').strip()
                    last_name = row.get('last_name', '').strip()
                    email = row.get('email', '').strip()

                    if not first_name:
                        raise ValueError("First name is required")
                    if not last_name:
                        raise ValueError("Last name is required")
                    if not email:
                        raise ValueError("Email is required")

                    # Check for duplicate by email
                    existing = Contact.query.filter_by(
                        tenant_id=tenant_id,
                        email=email
                    ).first()

                    if existing:
                        raise ValueError(f"Contact with email '{email}' already exists")

                    # Look up company by name if provided
                    company_id = None
                    company_name = row.get('company_name', '').strip()
                    if company_name:
                        company = Company.query.filter_by(
                            tenant_id=tenant_id,
                            name=company_name
                        ).first()
                        if company:
                            company_id = company.id

                    # Parse lead_score as integer
                    lead_score = 0
                    try:
                        lead_score_str = row.get('lead_score', '0').strip()
                        if lead_score_str:
                            lead_score = int(lead_score_str)
                    except ValueError:
                        pass  # Use default 0

                    # Normalize phone numbers to E.164 format
                    phone_raw = row.get('phone', '').strip()
                    phone_normalized = normalize_phone_number(phone_raw) if phone_raw else None

                    mobile_raw = row.get('mobile', '').strip()
                    mobile_normalized = normalize_phone_number(mobile_raw) if mobile_raw else None

                    # Create contact
                    contact = Contact(
                        tenant_id=tenant_id,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone=phone_normalized,
                        mobile=mobile_normalized,
                        job_title=row.get('job_title', '').strip() or None,
                        department=row.get('department', '').strip() or None,
                        seniority_level=row.get('seniority_level', '').strip() or None,
                        company_id=company_id,
                        linkedin_url=row.get('linkedin_url', '').strip() or None,
                        twitter_handle=row.get('twitter_handle', '').strip() or None,
                        preferred_contact_method=row.get('preferred_contact_method', '').strip() or None,
                        timezone=row.get('timezone', '').strip() or None,
                        description=row.get('description', '').strip() or None,
                        tags=row.get('tags', '').strip() or None,
                        status=row.get('status', 'active').strip() or 'active',
                        lead_source=row.get('lead_source', '').strip() or None,
                        lead_score=lead_score,
                        lifecycle_stage=row.get('lifecycle_stage', 'subscriber').strip() or 'subscriber',
                        owner_id=owner_id
                    )

                    db.session.add(contact)
                    db.session.flush()  # Get the ID without committing

                    results['success'] += 1
                    results['created_ids'].append(contact.id)

                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'row': row_num,
                        'data': dict(row),
                        'error': str(e)
                    })
                    db.session.rollback()

            # Commit all successful imports
            if results['success'] > 0:
                db.session.commit()

        except Exception as e:
            db.session.rollback()
            results['errors'].append({
                'row': 0,
                'data': {},
                'error': f"CSV parsing error: {str(e)}"
            })
            results['failed'] = results['total']
            results['success'] = 0

        return results

    @staticmethod
    def generate_company_template():
        """Generate CSV template for company import"""
        headers = [
            'name',
            'website',
            'industry',
            'company_size',
            'annual_revenue',
            'address_street',
            'address_city',
            'address_state',
            'address_postal_code',
            'address_country',
            'phone',
            'linkedin_url',
            'twitter_handle',
            'description',
            'tags',
            'status',
            'lifecycle_stage'
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        # Add sample row
        writer.writerow([
            'Acme Corporation',
            'https://acme.example.com',
            'Technology',
            '51-200',
            '$10M-50M',
            '123 Main St',
            'San Francisco',
            'CA',
            '94102',
            'USA',
            '+1-555-0100',
            'https://linkedin.com/company/acme',
            '@acmecorp',
            'Leading provider of innovative solutions',
            'tech,saas,b2b',
            'active',
            'customer'
        ])

        return output.getvalue()

    @staticmethod
    def generate_contact_template():
        """Generate CSV template for contact import"""
        headers = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'mobile',
            'job_title',
            'department',
            'seniority_level',
            'company_name',
            'linkedin_url',
            'twitter_handle',
            'preferred_contact_method',
            'timezone',
            'description',
            'tags',
            'status',
            'lead_source',
            'lead_score',
            'lifecycle_stage'
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        # Add sample row
        writer.writerow([
            'John',
            'Doe',
            'john.doe@example.com',
            '+1-555-0101',
            '+1-555-0102',
            'VP of Engineering',
            'Engineering',
            'VP',
            'Acme Corporation',
            'https://linkedin.com/in/johndoe',
            '@johndoe',
            'email',
            'America/Los_Angeles',
            'Key decision maker for engineering purchases',
            'technical,decision-maker',
            'active',
            'referral',
            '85',
            'opportunity'
        ])

        return output.getvalue()
