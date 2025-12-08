"""
Competitor Identification Service
Discovers potential competitors using multiple strategies
"""
import json
import os
import requests
from typing import List, Dict, Optional
from anthropic import Anthropic
from app import db
from app.models.tenant import Tenant
from app.models.company_enrichment_cache import CompanyEnrichmentCache


class CompetitorIdentificationService:
    """Service for discovering and validating competitor companies"""

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.anthropic_client = Anthropic(api_key=api_key)
        self.timeout = 10  # seconds for HTTP requests

    def suggest_competitors(self, tenant_id: int, limit: int = 10) -> List[Dict]:
        """
        Suggest competitors using multiple strategies:
        1. Parse workspace business_context if available
        2. Use Claude to identify based on industry + products
        3. Cross-reference CompanyEnrichmentCache.competitors
        4. Validate and score results

        Args:
            tenant_id: The tenant ID to find competitors for
            limit: Maximum number of competitors to suggest

        Returns:
            List of dictionaries with competitor information:
            [{"name": str, "website": str, "confidence": float, "source": str}]
        """
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return []

        competitors = []
        seen_domains = set()

        # Strategy 1: Check existing enrichment cache for competitor data
        enrichment_competitors = self._get_competitors_from_enrichment_cache(tenant)
        for comp in enrichment_competitors:
            if comp['website'] not in seen_domains:
                competitors.append(comp)
                seen_domains.add(comp['website'])

        # Strategy 2: Use Claude AI to identify competitors based on business context
        try:
            # Build business data from all available sources
            business_data = self._build_business_data(tenant)
            print(f"[COMPETITOR] Business data for {tenant.name}: {business_data}")

            # Check if we have sufficient context for AI suggestions
            has_context = (
                (business_data.get('company_description', '') and
                 business_data['company_description'] != f'{tenant.name} company') or
                business_data.get('industry', 'business') != 'business' or
                business_data.get('products_services') or
                business_data.get('target_market') or
                business_data.get('website_url')
            )

            if not has_context:
                print(f"[COMPETITOR] Insufficient context for {tenant.name}. Skipping AI suggestions.")
                print(f"[COMPETITOR] Available: description={business_data.get('company_description')}, "
                      f"industry={business_data.get('industry')}, "
                      f"products={len(business_data.get('products_services', []))}, "
                      f"website_url={business_data.get('website_url')}")
            else:
                ai_competitors = self._identify_competitors_with_ai(business_data, tenant.name, limit)
                print(f"[COMPETITOR] AI identified {len(ai_competitors)} competitors")

                for comp in ai_competitors:
                    if comp['website'] not in seen_domains:
                        competitors.append(comp)
                        seen_domains.add(comp['website'])

        except Exception as e:
            print(f"[COMPETITOR] Error in AI suggestion: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        # Sort by confidence score (descending) and limit results
        competitors.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return competitors[:limit]

    def _get_competitors_from_enrichment_cache(self, tenant: Tenant) -> List[Dict]:
        """
        Extract competitors from existing company enrichment cache

        Args:
            tenant: The tenant to search for

        Returns:
            List of competitor dictionaries
        """
        competitors = []

        # Query enrichment cache for companies with competitor data
        cached_companies = CompanyEnrichmentCache.query.filter(
            CompanyEnrichmentCache.competitors.isnot(None)
        ).limit(50).all()

        for cached in cached_companies:
            if cached.competitors:
                try:
                    competitor_list = json.loads(cached.competitors) if isinstance(cached.competitors, str) else cached.competitors

                    for comp in competitor_list:
                        if isinstance(comp, dict) and comp.get('name') and comp.get('domain'):
                            competitors.append({
                                'name': comp['name'],
                                'website': comp['domain'],
                                'confidence': 0.7,  # Medium confidence from cache
                                'source': 'enrichment_cache'
                            })
                except (json.JSONDecodeError, TypeError):
                    continue

        return competitors

    def _build_business_data(self, tenant: Tenant) -> Dict:
        """
        Build comprehensive business data from all available sources:
        1. Auto-scraped business_context (JSON)
        2. User-provided custom_context (markdown/text)
        3. Tenant's website data
        4. Fallback to minimal data

        Args:
            tenant: The tenant to build business data for

        Returns:
            Dictionary with business information
        """
        business_data = {
            'company_description': '',
            'industry': 'business',
            'products_services': [],
            'target_market': '',
            'website_url': tenant.website_url or ''
        }

        # Source 1: Auto-scraped business_context (highest priority for structured data)
        if tenant.business_context:
            try:
                scraped_data = json.loads(tenant.business_context)
                business_data.update(scraped_data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Source 2: User-provided custom_context (adds human insight)
        if tenant.custom_context:
            # Append custom context to description
            custom_text = tenant.custom_context.strip()
            if custom_text:
                current_desc = business_data.get('company_description', '')
                if current_desc:
                    business_data['company_description'] = f"{current_desc}\n\nAdditional Context: {custom_text}"
                else:
                    business_data['company_description'] = custom_text

        # Source 3: Tenant's website content (if we have it)
        if tenant.website and hasattr(tenant.website, 'title'):
            # Use website title and tagline if available
            if tenant.website.title and not business_data.get('company_description'):
                business_data['company_description'] = tenant.website.title
            if hasattr(tenant.website, 'tagline') and tenant.website.tagline:
                tagline = tenant.website.tagline.strip()
                if tagline:
                    current_desc = business_data.get('company_description', '')
                    business_data['company_description'] = f"{current_desc}\n{tagline}" if current_desc else tagline

        # Fallback: If still no description, use company name
        if not business_data.get('company_description'):
            business_data['company_description'] = f'{tenant.name} company'

        return business_data

    def _identify_competitors_with_ai(self, business_data: Dict, company_name: str, limit: int) -> List[Dict]:
        """
        Use Claude to identify competitors based on business context

        Args:
            business_data: Parsed business_context JSON
            company_name: The company's name
            limit: Max competitors to identify

        Returns:
            List of competitor dictionaries
        """
        # Build AI prompt
        prompt = self._build_competitor_identification_prompt(business_data, company_name, limit)

        try:
            print(f"[COMPETITOR] Calling Claude API with prompt length: {len(prompt)}")

            # Call Claude API
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response.content[0].text
            print(f"[COMPETITOR] Claude response length: {len(response_text)}")

            # Extract JSON from response
            competitors = self._parse_competitor_json(response_text)
            print(f"[COMPETITOR] Parsed {len(competitors)} competitors from response")

            # Validate and enrich with domain discovery
            validated_competitors = []
            for comp in competitors:
                validated = self._validate_and_enrich_competitor(comp)
                if validated:
                    validated_competitors.append(validated)
                    print(f"[COMPETITOR] Validated: {comp['name']} -> {validated['website']}")
                else:
                    print(f"[COMPETITOR] Failed validation: {comp['name']}")

            print(f"[COMPETITOR] Returning {len(validated_competitors)} validated competitors")
            return validated_competitors

        except Exception as e:
            print(f"[COMPETITOR] Error identifying competitors with AI: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _build_competitor_identification_prompt(self, business_data: Dict, company_name: str, limit: int) -> str:
        """Build the AI prompt for competitor identification"""

        industry = business_data.get('industry', 'business')
        description = business_data.get('company_description', '')
        products = business_data.get('products_services', [])
        target_market = business_data.get('target_market', '')
        website_url = business_data.get('website_url', '')

        products_str = ', '.join(products[:5]) if products else 'N/A'

        # Build context section based on available data
        context_parts = []
        if website_url:
            context_parts.append(f"- Website: {website_url}")
        if description and description != f'{company_name} company':
            context_parts.append(f"- Description: {description}")
        if industry and industry != 'business':
            context_parts.append(f"- Industry: {industry}")
        if products and products_str != 'N/A':
            context_parts.append(f"- Products/Services: {products_str}")
        if target_market:
            context_parts.append(f"- Target Market: {target_market}")

        context_str = '\n'.join(context_parts) if context_parts else "Limited information available."

        prompt = f"""Identify the top {limit} potential competitors for {company_name}.

Company Information:
{context_str}

Based on the company name, website, and available context, please identify {limit} companies that compete with {company_name}. For each competitor, provide:
1. Company name
2. Primary domain/website (just the domain, not full URL - e.g. "example.com" not "https://example.com")
3. Brief reason why they're a competitor (one sentence)

If limited information is available, make reasonable inferences based on the company name and industry context.

Return your response as a JSON array with this exact structure:
[
  {{
    "name": "Competitor Company Name",
    "domain": "competitor.com",
    "reason": "Brief reason"
  }}
]

IMPORTANT: Return ONLY the JSON array, no additional text or explanation."""

        return prompt

    def _parse_competitor_json(self, response_text: str) -> List[Dict]:
        """Parse JSON from Claude's response"""
        try:
            # Try to find JSON array in response
            start = response_text.find('[')
            end = response_text.rfind(']') + 1

            if start != -1 and end > start:
                json_str = response_text[start:end]
                competitors = json.loads(json_str)

                # Validate structure
                if isinstance(competitors, list):
                    return [c for c in competitors if isinstance(c, dict) and c.get('name') and c.get('domain')]

        except (json.JSONDecodeError, ValueError):
            pass

        return []

    def _validate_and_enrich_competitor(self, competitor: Dict) -> Optional[Dict]:
        """
        Validate competitor data and enrich with additional info

        Args:
            competitor: Dictionary with 'name' and 'domain' keys

        Returns:
            Enriched competitor dictionary or None if invalid
        """
        name = competitor.get('name')
        domain = competitor.get('domain', '').strip().lower()

        if not name or not domain:
            return None

        # Remove http/https if present
        domain = domain.replace('http://', '').replace('https://', '')
        domain = domain.split('/')[0]  # Remove path if present

        # Validate domain is accessible
        validation = self.validate_competitor_url(domain)

        if not validation['valid']:
            # If domain validation fails, try to find correct domain
            found_domain = self.find_competitor_domain(name)
            if found_domain:
                domain = found_domain
            else:
                return None  # Skip if we can't find a valid domain

        return {
            'name': name,
            'website': domain,
            'confidence': 0.85,  # High confidence from AI
            'source': 'ai_suggested',
            'reason': competitor.get('reason', '')
        }

    def validate_competitor_url(self, url: str) -> Dict:
        """
        Verify competitor URL is accessible

        Args:
            url: Domain or URL to validate

        Returns:
            Dictionary with 'valid', 'domain', and optional 'error' keys
        """
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            # Extract domain
            domain = url.replace('https://', '').replace('http://', '').split('/')[0]

            # Try to fetch the website
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; SoloquyBot/1.0; +https://soloquy.com)'
            }

            response = requests.head(url, headers=headers, timeout=self.timeout, allow_redirects=True)

            if response.status_code < 400:
                return {
                    'valid': True,
                    'domain': domain
                }
            else:
                return {
                    'valid': False,
                    'domain': domain,
                    'error': f'HTTP {response.status_code}'
                }

        except requests.RequestException as e:
            return {
                'valid': False,
                'domain': url,
                'error': str(e)
            }

    def find_competitor_domain(self, company_name: str) -> Optional[str]:
        """
        Leverage LeadEnrichmentService to find company domain from Google search

        Args:
            company_name: The competitor's company name

        Returns:
            Domain string or None if not found
        """
        try:
            from app.services.lead_enrichment_service import lead_enrichment_service

            # Use existing service to find domain via Google
            domain = lead_enrichment_service.find_domain_from_google(company_name)

            if domain and domain != 'N/A':
                return domain

        except Exception as e:
            print(f"Error finding domain for {company_name}: {e}")

        return None


# Singleton instance
competitor_identification_service = CompetitorIdentificationService()
