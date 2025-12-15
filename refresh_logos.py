"""
Refresh company logos to use Google's favicon service
Replaces old Clearbit URLs with Google favicon URLs
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.company import Company
from urllib.parse import urlparse

def get_google_favicon_url(domain):
    """Get Google favicon URL for a domain"""
    if not domain:
        return None
    # Remove protocol and path, keep just domain
    if '://' in domain:
        domain = urlparse(domain).netloc or domain
    domain = domain.split('/')[0]
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

def refresh_company_logos():
    """Refresh logos for all companies"""
    app = create_app()
    
    with app.app_context():
        # Get all companies with websites
        companies = Company.query.filter(Company.website.isnot(None)).all()
        
        print(f"Found {len(companies)} companies with websites")
        
        updated_count = 0
        for company in companies:
            if company.website:
                # Extract domain from website
                domain = company.website
                if '://' in domain:
                    domain = urlparse(domain).netloc or domain
                domain = domain.split('/')[0]
                
                # Generate new logo URL
                new_logo_url = get_google_favicon_url(domain)
                
                # Update if different or if using old Clearbit URL
                if company.logo_url != new_logo_url:
                    old_url = company.logo_url
                    company.logo_url = new_logo_url
                    updated_count += 1
                    print(f"Updated {company.name}: {domain}")
        
        # Commit all changes
        if updated_count > 0:
            db.session.commit()
            print(f"\n✓ Successfully updated {updated_count} company logos")
        else:
            print("\n✓ All logos are already up to date")

if __name__ == "__main__":
    refresh_company_logos()
