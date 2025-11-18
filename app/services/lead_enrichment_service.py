"""
Lead Enrichment Service
Automatically enriches company data using web scraping, Google search, and AI analysis
"""
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

from app import db
from app.models.company import Company
from app.models.company_enrichment_cache import CompanyEnrichmentCache
from app.models.activity import Activity
from app.models.agent import Agent
from app.services.ai_service import get_ai_service


class LeadEnrichmentService:
    """Service for enriching company leads with business intelligence"""

    def __init__(self):
        self.ai_service = get_ai_service()

    @staticmethod
    def extract_domain_from_url(url):
        """Extract clean domain from URL (e.g., 'https://www.acme.com' -> 'acme.com')"""
        if not url:
            return None

        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Remove 'www.' prefix
            domain = re.sub(r'^www\.', '', domain)
            return domain.lower()
        except Exception:
            return None

    @staticmethod
    def extract_domain_from_email(email):
        """Extract domain from email address (e.g., 'john@acme.com' -> 'acme.com')"""
        if not email or '@' not in email:
            return None
        return email.split('@')[1].lower()

    def get_company_domain(self, company):
        """Get the best domain for a company from website or contact emails"""
        # Try website first
        if company.website:
            domain = self.extract_domain_from_url(company.website)
            if domain:
                return domain

        # Try contact emails
        for contact in company.contacts:
            if contact.email:
                domain = self.extract_domain_from_email(contact.email)
                if domain:
                    return domain

        return None

    def get_company_logo(self, domain):
        """
        Fetch company logo URL using Clearbit Logo API
        Returns logo URL or None if not available
        """
        if not domain:
            return None

        # Clearbit Logo API - free, no API key required
        logo_url = f"https://logo.clearbit.com/{domain}"

        try:
            # Verify the logo exists by making a HEAD request
            response = requests.head(logo_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return logo_url
        except Exception as e:
            print(f"Error fetching logo for {domain}: {str(e)}")

        return None

    def fetch_website_html(self, url, timeout=10):
        """Fetch HTML content from a website"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; SoloquyBot/1.0; +https://soloquy.com)'
            }
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return None

    def parse_website_content(self, html):
        """Extract key content from HTML"""
        if not html:
            return {}

        try:
            soup = BeautifulSoup(html, 'lxml')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Extract meta tags
            meta_description = soup.find('meta', attrs={'name': 'description'})
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})

            # Extract headings
            h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
            h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]

            # Get main text content (limit to first 5000 chars)
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            text = text[:5000]  # Limit text length

            return {
                'meta_description': meta_description.get('content') if meta_description else None,
                'meta_keywords': meta_keywords.get('content') if meta_keywords else None,
                'h1_headings': h1_tags[:5],  # First 5 H1s
                'h2_headings': h2_tags[:10],  # First 10 H2s
                'body_text': text
            }
        except Exception as e:
            print(f"Error parsing HTML: {str(e)}")
            return {}

    def google_search_company(self, company_name, domain=None):
        """
        Perform Google search for a company to gather additional context
        Uses web scraping approach to get search results
        """
        try:
            import urllib.parse
            search_query = f"{company_name}"
            if domain:
                search_query += f" {domain}"
            search_query += " company about"

            encoded_query = urllib.parse.quote_plus(search_query)
            search_url = f"https://www.google.com/search?q={encoded_query}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            response = requests.get(search_url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # Extract search result snippets
                snippets = []
                for result in soup.find_all('div', class_='VwiC3b', limit=5):
                    snippet_text = result.get_text(strip=True)
                    if snippet_text and len(snippet_text) > 20:
                        snippets.append(snippet_text)

                # Also try to extract from meta descriptions in results
                for result in soup.find_all('span', class_='aCOpRe', limit=5):
                    snippet_text = result.get_text(strip=True)
                    if snippet_text and len(snippet_text) > 20:
                        snippets.append(snippet_text)

                return {
                    'search_performed': True,
                    'query': search_query,
                    'snippets': snippets[:5],  # Top 5 snippets
                    'snippet_text': ' | '.join(snippets[:5]) if snippets else None
                }
            else:
                print(f"Google search returned status {response.status_code}")
                return {
                    'search_performed': False,
                    'query': search_query,
                    'error': f'HTTP {response.status_code}'
                }

        except Exception as e:
            print(f"Error performing Google search: {str(e)}")
            return {
                'search_performed': False,
                'query': search_query if 'search_query' in locals() else company_name,
                'error': str(e)
            }

    def get_or_create_cache(self, domain):
        """Get existing cache or create new entry"""
        cache = CompanyEnrichmentCache.query.filter_by(domain=domain).first()

        # Check if cache exists and is not expired
        if cache and not cache.is_expired():
            cache.refresh_ttl()  # Extend TTL
            db.session.commit()
            return cache, False  # False = not newly created

        # Create new cache entry
        if cache:
            # Update existing expired cache
            cache.scraped_at = datetime.utcnow()
            cache.ttl_expires_at = CompanyEnrichmentCache.get_default_ttl()
            return cache, True  # True = needs refresh
        else:
            # Create brand new cache
            cache = CompanyEnrichmentCache(
                domain=domain,
                scraped_at=datetime.utcnow(),
                ttl_expires_at=CompanyEnrichmentCache.get_default_ttl()
            )
            db.session.add(cache)
            db.session.flush()  # Get ID without committing
            return cache, True  # True = needs scraping

    def analyze_with_ai(self, company_name, website_data, search_data, agent):
        """Use AI to analyze company and generate enrichment data"""

        # Build context for AI
        context = f"""
Company Name: {company_name}

Website Data:
{json.dumps(website_data, indent=2)}

Google Search Results:
{json.dumps(search_data, indent=2)}

Analyze this company and provide a comprehensive assessment. For company size, look for clues like:
- Number of employees mentioned on website or in search results
- LinkedIn employee count estimates
- Office locations (multiple locations = larger company)
- Team page size
- Funding announcements or revenue figures
- Use these categories: "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001+"

Provide your analysis in the following JSON format:
{{
    "company_basics": {{
        "industry": "specific industry/vertical",
        "company_size_estimate": "1-10|11-50|51-200|201-500|501-1000|1001-5000|5001+",
        "description": "2-3 sentence company description",
        "founding_year": "YYYY or null",
        "headquarters": "City, State/Country or null"
    }},
    "products_services": {{
        "primary_offerings": ["product1", "product2", "product3"],
        "target_market": "description of target customers and market segment",
        "value_proposition": "key value propositions and differentiators"
    }},
    "competitors": {{
        "main_competitors": ["competitor1", "competitor2", "competitor3"],
        "market_position": "leader|challenger|niche player|startup|unknown",
        "competitive_advantages": ["advantage1", "advantage2"]
    }},
    "key_people": {{
        "executives": [
            {{"name": "Full Name", "title": "Job Title", "linkedin": "url or null"}}
        ]
    }},
    "lead_analysis": {{
        "lead_score": 75,
        "lead_score_rationale": "detailed explanation of score based on company size, market position, funding, growth indicators",
        "buying_signals": ["specific signals like hiring, funding, expansion, tech stack"],
        "competitive_position": "detailed market position and competitive landscape analysis",
        "enrichment_summary": "executive summary highlighting key insights and opportunity assessment"
    }}
}}

Provide ONLY valid JSON, no additional text. Be thorough in your analysis and base conclusions on available data.
"""

        try:
            # Use the Lead Analyzer agent to analyze
            response = self.ai_service.chat(
                agent=agent,
                messages=[{"role": "user", "content": context}],
                system_prompt=agent.system_prompt
            )

            # Extract JSON from response
            content = response['content']

            # Try to find JSON in code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to parse the entire response as JSON
                json_str = content

            analysis = json.loads(json_str)
            return analysis

        except Exception as e:
            print(f"Error in AI analysis: {str(e)}")
            # Return default structure on error
            return {
                "company_basics": {"description": "Analysis failed"},
                "products_services": {},
                "competitors": {},
                "key_people": {},
                "lead_analysis": {
                    "lead_score": 50,
                    "lead_score_rationale": f"Analysis error: {str(e)}",
                    "buying_signals": [],
                    "competitive_position": "Unknown",
                    "enrichment_summary": "Enrichment analysis encountered an error"
                }
            }

    def enrich_company(self, company_id, tenant_id):
        """
        Main enrichment function - orchestrates the entire enrichment workflow
        This is called as a background job
        """
        try:
            # Fetch company
            company = Company.query.filter_by(id=company_id, tenant_id=tenant_id).first()
            if not company:
                print(f"Company {company_id} not found")
                return

            # Update status to processing
            company.enrichment_status = 'processing'
            db.session.commit()

            # Get Lead Analyzer agent (join through Department since Agent doesn't have tenant_id directly)
            from app.models.department import Department
            agent = Agent.query.join(Department).filter(
                Department.tenant_id == tenant_id,
                Agent.name == 'Lead Analyzer'
            ).first()

            if not agent:
                print("Lead Analyzer agent not found - using first available agent")
                # Use any agent from this tenant as fallback
                agent = Agent.query.join(Department).filter(
                    Department.tenant_id == tenant_id
                ).first()

            # Step 1: Extract domain
            domain = self.get_company_domain(company)
            if not domain:
                company.enrichment_status = 'failed'
                company.enrichment_error = 'No domain found (no website or contact emails)'
                db.session.commit()
                return

            # Step 1.5: Fetch company logo
            logo_url = self.get_company_logo(domain)
            if logo_url:
                company.logo_url = logo_url
                print(f"Found logo for {company.name}: {logo_url}")

            # Step 2: Check cache
            cache, needs_scraping = self.get_or_create_cache(domain)

            # Step 3: Scrape website if needed
            if needs_scraping:
                print(f"Scraping website for domain: {domain}")
                html = self.fetch_website_html(domain)
                cache.raw_html = html[:100000] if html else None  # Store first 100KB

                website_data = self.parse_website_content(html)

                # Step 4: Google search (placeholder)
                search_data = self.google_search_company(company.name, domain)

                # Step 5: AI Analysis
                if agent:
                    print(f"Analyzing with AI agent: {agent.name}")
                    analysis = self.analyze_with_ai(company.name, website_data, search_data, agent)

                    # Store in cache
                    cache.company_basics = json.dumps(analysis.get('company_basics', {}))
                    cache.products_services = json.dumps(analysis.get('products_services', {}))
                    cache.competitors = json.dumps(analysis.get('competitors', {}))
                    cache.key_people = json.dumps(analysis.get('key_people', {}))

                    # Extract social URLs if found
                    # (In production, this would parse from HTML or search results)
                    cache.linkedin_company_url = None  # TODO: Extract from analysis
                    cache.twitter_handle = None  # TODO: Extract from analysis

                    db.session.commit()
                else:
                    analysis = {
                        "lead_analysis": {
                            "lead_score": 50,
                            "lead_score_rationale": "No agent available",
                            "buying_signals": [],
                            "competitive_position": "Unknown",
                            "enrichment_summary": "Enrichment completed without AI analysis"
                        }
                    }
            else:
                print(f"Using cached data for domain: {domain}")
                # Load analysis from cache
                analysis = {
                    "company_basics": json.loads(cache.company_basics) if cache.company_basics else {},
                    "products_services": json.loads(cache.products_services) if cache.products_services else {},
                    "competitors": json.loads(cache.competitors) if cache.competitors else {},
                    "key_people": json.loads(cache.key_people) if cache.key_people else {},
                    "lead_analysis": {}
                }

                # Re-analyze for tenant-specific lead scoring
                if agent:
                    website_data = self.parse_website_content(cache.raw_html)
                    search_data = {'cached': True}
                    full_analysis = self.analyze_with_ai(company.name, website_data, search_data, agent)
                    analysis["lead_analysis"] = full_analysis.get("lead_analysis", {})

            # Step 6: Update company record with tenant-specific analysis
            company.enrichment_cache_id = cache.id
            lead_analysis = analysis.get('lead_analysis', {})

            company.lead_score = lead_analysis.get('lead_score', 50)
            company.buying_signals = json.dumps(lead_analysis.get('buying_signals', []))
            company.competitive_position = lead_analysis.get('competitive_position', '')
            company.enrichment_summary = lead_analysis.get('enrichment_summary', '')

            # Update company basics from cache if not already set
            basics = analysis.get('company_basics', {})
            if basics.get('industry') and not company.industry:
                company.industry = basics['industry']
            if basics.get('company_size_estimate') and not company.company_size:
                company.company_size = basics['company_size_estimate']
            if basics.get('description') and not company.description:
                company.description = basics['description']

            company.enrichment_status = 'completed'
            company.enriched_at = datetime.utcnow()
            company.enrichment_error = None

            # Step 7: Create activity log
            activity = Activity(
                tenant_id=tenant_id,
                activity_type='enrichment',
                subject='Lead enrichment completed',
                description=f'AI analyzed {company.name} and assigned lead score: {company.lead_score}/100',
                company_id=company.id,
                completed=True,
                completed_at=datetime.utcnow(),
                created_by_id=company.owner_id or 1,  # Use owner or system user
                created_at=datetime.utcnow()
            )
            db.session.add(activity)

            db.session.commit()
            print(f"Successfully enriched company: {company.name} (score: {company.lead_score})")

        except Exception as e:
            print(f"Error enriching company {company_id}: {str(e)}")
            db.session.rollback()

            # Update company with error
            company = Company.query.get(company_id)
            if company:
                company.enrichment_status = 'failed'
                company.enrichment_error = str(e)
                db.session.commit()


# Background job function (called by RQ worker)
def enrich_company_background(company_id, tenant_id):
    """
    Background job entry point for company enrichment
    This function is called by the RQ worker
    """
    service = LeadEnrichmentService()
    service.enrich_company(company_id, tenant_id)
