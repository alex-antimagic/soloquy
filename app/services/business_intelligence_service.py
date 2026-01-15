"""
Business Intelligence Service
Scrapes and analyzes company websites to provide context to AI agents
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, Optional
from anthropic import Anthropic
from app import db
from app.models.tenant import Tenant


class BusinessIntelligenceService:
    """Service for extracting business intelligence from company websites"""

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.anthropic_client = Anthropic(api_key=api_key)
        self.timeout = 10  # seconds for HTTP requests

    def scrape_business_context(self, tenant_id: int) -> Dict:
        """
        Scrape and analyze a tenant's website to extract business context.

        Args:
            tenant_id: The ID of the tenant to scrape

        Returns:
            Dictionary with business intelligence
        """
        tenant = Tenant.query.get(tenant_id)
        if not tenant or not tenant.website_url:
            return {'error': 'No website URL provided'}

        try:
            # Update status
            tenant.context_scraping_status = 'processing'
            db.session.commit()

            # Step 1: Fetch website content
            website_content = self._fetch_website_content(tenant.website_url)

            # Step 2: Use Claude to analyze the content
            business_context = self._analyze_with_claude(website_content, tenant.name)

            # Step 3: Store the context
            tenant.business_context = json.dumps(business_context, indent=2)
            tenant.context_scraped_at = datetime.utcnow()
            tenant.context_scraping_status = 'completed'
            tenant.context_scraping_error = None
            db.session.commit()

            return business_context

        except Exception as e:
            # Handle errors gracefully
            error_msg = str(e)
            tenant.context_scraping_status = 'failed'
            tenant.context_scraping_error = error_msg
            db.session.commit()
            return {'error': error_msg}

    def _fetch_website_content(self, url: str) -> str:
        """
        Fetch website content with error handling
        """
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; WorkleadBot/1.0; +https://worklead.ai)'
        }

        response = requests.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
        response.raise_for_status()

        # Get text content, truncate if too long (Claude has token limits)
        content = response.text[:100000]  # ~100KB limit
        return content

    def _analyze_with_claude(self, html_content: str, company_name: str) -> Dict:
        """
        Use Claude to intelligently analyze website content and extract business intelligence
        """

        analysis_prompt = f"""Analyze this company website for {company_name} and extract key business intelligence.

HTML Content:
{html_content}

Please analyze and provide a structured JSON response with the following information:

1. company_description: A 2-3 sentence summary of what the company does
2. industry: The primary industry/sector (e.g., "SaaS", "E-commerce", "Healthcare", "Consulting")
3. products_services: List of main products or services offered (array of strings, max 5)
4. target_market: Who their customers are (e.g., "Small businesses", "Enterprise", "Consumers")
5. value_proposition: Their unique selling points or key differentiators (1-2 sentences)
6. company_stage: Best guess at company stage ("Startup", "Growth", "Established", "Enterprise")
7. key_topics: List of important topics/themes relevant to this business (for agent context, max 5)

Return ONLY valid JSON, no markdown formatting or explanation."""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",  # Use Sonnet for better analysis
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for more consistent extraction
                messages=[{
                    "role": "user",
                    "content": analysis_prompt
                }]
            )

            # Extract and parse JSON response
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                # Remove first line (```) and last line (```)
                response_text = '\n'.join(lines[1:-1])
                # Remove 'json' if it's at the start
                if response_text.startswith('json'):
                    response_text = response_text[4:].strip()

            business_context = json.loads(response_text)
            return business_context

        except json.JSONDecodeError as e:
            return {
                'error': 'Failed to parse Claude response',
                'raw_response': response_text[:500]  # Truncate for safety
            }
        except Exception as e:
            return {'error': f'Claude analysis failed: {str(e)}'}


# Singleton instance
_bi_service = None

def get_bi_service() -> BusinessIntelligenceService:
    """Get or create the business intelligence service singleton"""
    global _bi_service
    if _bi_service is None:
        _bi_service = BusinessIntelligenceService()
    return _bi_service


def scrape_business_context_async(tenant_id: int):
    """
    Asynchronously scrape business context for a tenant.
    For now, this is synchronous but isolated in a function for easy future async migration.
    """
    try:
        service = get_bi_service()
        service.scrape_business_context(tenant_id)
    except Exception as e:
        print(f"Error scraping business context for tenant {tenant_id}: {e}")
