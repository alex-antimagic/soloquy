"""
Similar Lead Discovery Service
Discovers potential leads similar to existing customers using AI and enrichment cache
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from anthropic import Anthropic
from app import db
from app.models.company import Company
from app.models.lead import Lead
from app.models.similar_lead_discovery import SimilarLeadDiscovery
from app.models.company_enrichment_cache import CompanyEnrichmentCache
from app.services.competitor_identification_service import CompetitorIdentificationService


class SimilarLeadDiscoveryService:
    """Service for discovering similar leads based on reference customers"""

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.anthropic_client = Anthropic(api_key=api_key)
        self.competitor_service = CompetitorIdentificationService()
        self.timeout = 10  # seconds for HTTP requests

    def create_discovery(self, tenant_id: int, reference_company_id: int,
                        criteria: Dict, max_results: int = 20,
                        initiated_by: str = 'ui', user_id: int = None,
                        agent_id: int = None) -> SimilarLeadDiscovery:
        """
        Create discovery job and queue for background processing

        Args:
            tenant_id: Tenant ID
            reference_company_id: ID of reference company to find similar leads for
            criteria: Similarity criteria dict {industry, business_model, tech_stack, company_size}
            max_results: Maximum number of similar leads to discover
            initiated_by: 'agent', 'ui', or 'api'
            user_id: User who initiated (if applicable)
            agent_id: Agent who initiated (if applicable)

        Returns:
            SimilarLeadDiscovery instance with status='pending'
        """
        # Get reference company name for display
        reference_company = Company.query.get(reference_company_id)
        if not reference_company:
            raise ValueError(f"Reference company {reference_company_id} not found")

        # Create discovery record
        discovery = SimilarLeadDiscovery(
            tenant_id=tenant_id,
            reference_company_id=reference_company_id,
            reference_company_name=reference_company.name,
            similarity_criteria=json.dumps(criteria),
            max_results=max_results,
            status='pending',
            progress_percentage=0,
            initiated_by=initiated_by,
            initiated_by_user_id=user_id,
            initiated_by_agent_id=agent_id
        )

        db.session.add(discovery)
        db.session.commit()

        # Queue background job
        from app.tasks import run_similar_lead_discovery
        run_similar_lead_discovery.delay(discovery.id)

        return discovery

    def run_discovery(self, discovery_id: int):
        """
        Main orchestration method - runs in background job

        1. Build reference company profile
        2. Execute discovery strategies (cache, AI, Google search)
        3. Score similarity using AI
        4. Auto-create leads
        5. Update discovery status

        Args:
            discovery_id: ID of SimilarLeadDiscovery to process
        """
        discovery = SimilarLeadDiscovery.query.get(discovery_id)
        if not discovery:
            return

        try:
            print(f"[SIMILAR_LEADS] Starting discovery {discovery_id} for {discovery.reference_company_name}")

            # Update status to processing
            discovery.status = 'processing'
            discovery.started_at = datetime.utcnow()
            discovery.progress_percentage = 10
            discovery.progress_message = "Building reference company profile..."
            db.session.commit()

            # Step 1: Build reference company profile
            reference_company = Company.query.get(discovery.reference_company_id)
            if not reference_company:
                raise ValueError("Reference company not found")

            reference_profile = self._build_company_profile(reference_company)
            print(f"[SIMILAR_LEADS] Reference profile: {reference_profile.get('name')}")

            criteria = json.loads(discovery.similarity_criteria)

            # Step 2: Execute discovery strategies
            all_discoveries = []
            seen_domains = set()

            # Strategy 1: Cache search (fast)
            discovery.progress_percentage = 20
            discovery.progress_message = "Searching enrichment cache..."
            db.session.commit()

            cache_results = self._discover_from_cache(
                reference_profile, criteria, discovery.tenant_id, discovery.max_results
            )
            print(f"[SIMILAR_LEADS] Cache search found {len(cache_results)} candidates")

            for result in cache_results:
                if result['domain'] not in seen_domains:
                    all_discoveries.append(result)
                    seen_domains.add(result['domain'])

            # Strategy 2: AI discovery (smart)
            discovery.progress_percentage = 50
            discovery.progress_message = "Using AI to identify similar companies..."
            db.session.commit()

            ai_results = self._discover_with_ai(
                reference_profile, criteria, discovery.max_results
            )
            print(f"[SIMILAR_LEADS] AI discovery found {len(ai_results)} candidates")

            for result in ai_results:
                if result['domain'] not in seen_domains:
                    all_discoveries.append(result)
                    seen_domains.add(result['domain'])

            # Strategy 3: Google search (comprehensive)
            discovery.progress_percentage = 70
            discovery.progress_message = "Searching the web for similar companies..."
            db.session.commit()

            google_results = self._discover_from_google(
                reference_profile, criteria, discovery.max_results // 2
            )
            print(f"[SIMILAR_LEADS] Google search found {len(google_results)} candidates")

            for result in google_results:
                if result['domain'] not in seen_domains:
                    all_discoveries.append(result)
                    seen_domains.add(result['domain'])

            # Step 3: Score similarity using AI
            discovery.progress_percentage = 80
            discovery.progress_message = "Scoring similarity for discovered companies..."
            db.session.commit()

            scored_discoveries = []
            for candidate in all_discoveries[:discovery.max_results * 2]:  # Score more than needed
                try:
                    similarity_result = self._score_similarity(
                        reference_profile, candidate, criteria
                    )
                    candidate['similarity_score'] = similarity_result['similarity_score']
                    candidate['similarity_rationale'] = similarity_result['rationale']
                    scored_discoveries.append(candidate)
                except Exception as e:
                    print(f"[SIMILAR_LEADS] Error scoring {candidate.get('name')}: {e}")
                    # Continue with other candidates

            # Sort by similarity score (descending) and limit results
            scored_discoveries.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            final_discoveries = scored_discoveries[:discovery.max_results]

            print(f"[SIMILAR_LEADS] Scored {len(scored_discoveries)} candidates, keeping top {len(final_discoveries)}")

            # Step 4: Auto-create leads
            discovery.progress_percentage = 90
            discovery.progress_message = "Creating lead records..."
            db.session.commit()

            self._create_leads_from_discoveries(discovery, final_discoveries)

            # Step 5: Complete discovery
            discovery.status = 'completed'
            discovery.completed_at = datetime.utcnow()
            discovery.progress_percentage = 100
            discovery.progress_message = "Discovery completed successfully"
            discovery.discovered_count = len(final_discoveries)
            discovery.discovered_companies = json.dumps(final_discoveries)
            discovery.discovery_summary = f"Found {discovery.leads_created} similar leads out of {len(final_discoveries)} discovered companies matching {reference_company.name}"
            db.session.commit()

            print(f"[SIMILAR_LEADS] Discovery {discovery_id} completed: {discovery.leads_created} leads created")

        except Exception as e:
            print(f"[SIMILAR_LEADS] Error in discovery {discovery_id}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

            discovery.status = 'failed'
            discovery.error_message = str(e)
            discovery.completed_at = datetime.utcnow()
            db.session.commit()
            raise

    def _build_company_profile(self, company: Company) -> Dict:
        """
        Extract comprehensive profile from company and enrichment cache

        Args:
            company: Company model instance

        Returns:
            Dictionary with company profile data
        """
        profile = {
            'name': company.name,
            'domain': company.website or '',
            'industry': company.industry or '',
            'company_size': company.company_size or '',
            'annual_revenue': company.annual_revenue or '',
            'description': company.description or '',
            'products_services': [],
            'tech_stack': {},
            'business_model': ''
        }

        # Try to get enrichment data from cache
        if company.enrichment_cache_id:
            cache = CompanyEnrichmentCache.query.get(company.enrichment_cache_id)
            if cache:
                try:
                    if cache.company_basics:
                        basics = json.loads(cache.company_basics) if isinstance(cache.company_basics, str) else cache.company_basics
                        profile['industry'] = basics.get('industry', profile['industry'])
                        profile['company_size'] = basics.get('size', profile['company_size'])
                        profile['description'] = basics.get('description', profile['description'])

                    if cache.products_services:
                        products = json.loads(cache.products_services) if isinstance(cache.products_services, str) else cache.products_services
                        profile['products_services'] = products.get('categories', [])
                        profile['business_model'] = products.get('business_model', '')

                except (json.JSONDecodeError, TypeError) as e:
                    print(f"[SIMILAR_LEADS] Error parsing enrichment cache: {e}")

        # Fallback to business_context if available
        if company.business_context and not profile['products_services']:
            try:
                business_data = json.loads(company.business_context) if isinstance(company.business_context, str) else company.business_context
                profile['products_services'] = business_data.get('products_services', [])
                profile['industry'] = business_data.get('industry', profile['industry'])
            except (json.JSONDecodeError, TypeError):
                pass

        return profile

    def _discover_from_cache(self, reference_profile: Dict, criteria: Dict,
                            tenant_id: int, limit: int) -> List[Dict]:
        """
        Strategy 1: Search enrichment cache for similar companies

        Args:
            reference_profile: Reference company profile
            criteria: Similarity criteria
            tenant_id: Tenant ID (to exclude existing leads/companies)
            limit: Max results to return

        Returns:
            List of candidate dictionaries
        """
        candidates = []

        # Get all cached companies with enrichment data
        cached_companies = CompanyEnrichmentCache.query.limit(100).all()

        for cached in cached_companies:
            try:
                # Skip if domain matches reference
                if cached.domain == reference_profile.get('domain'):
                    continue

                # Check if already exists in CRM
                if self._check_existing_lead_or_company(cached.domain, tenant_id):
                    continue

                # Parse cached data
                if not cached.company_basics:
                    continue

                basics = json.loads(cached.company_basics) if isinstance(cached.company_basics, str) else cached.company_basics

                # Apply criteria filtering
                matches = True

                if criteria.get('industry') and reference_profile.get('industry'):
                    cached_industry = basics.get('industry', '').lower()
                    ref_industry = reference_profile.get('industry', '').lower()
                    if cached_industry and ref_industry:
                        if cached_industry not in ref_industry and ref_industry not in cached_industry:
                            matches = False

                if criteria.get('company_size') and reference_profile.get('company_size'):
                    cached_size = basics.get('size', '').lower()
                    ref_size = reference_profile.get('company_size', '').lower()
                    if cached_size and ref_size:
                        if cached_size != ref_size:
                            matches = False

                if matches:
                    candidates.append({
                        'name': basics.get('name', cached.domain),
                        'domain': cached.domain,
                        'source': 'enrichment_cache',
                        'confidence': 0.7,
                        'industry': basics.get('industry', ''),
                        'company_size': basics.get('size', '')
                    })

                if len(candidates) >= limit:
                    break

            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                continue

        return candidates

    def _discover_with_ai(self, reference_profile: Dict, criteria: Dict,
                         limit: int) -> List[Dict]:
        """
        Strategy 2: Use Claude to identify similar companies

        Args:
            reference_profile: Reference company profile
            criteria: Similarity criteria
            limit: Max results to return

        Returns:
            List of candidate dictionaries
        """
        try:
            # Build AI prompt
            criteria_list = [k for k, v in criteria.items() if v]
            criteria_str = ', '.join(criteria_list)

            prompt = f"""Identify {limit} companies that are similar to this reference company:

Reference Company: {reference_profile['name']}
Domain: {reference_profile['domain']}
Industry: {reference_profile['industry']}
Company Size: {reference_profile['company_size']}
Products/Services: {', '.join(reference_profile.get('products_services', [])[:5])}
Description: {reference_profile.get('description', 'N/A')[:500]}

Find companies that match on these criteria: {criteria_str}

Requirements:
- Companies should be potential customers/leads (not competitors)
- Focus on companies in similar industries or with similar business models
- Include both well-known and emerging companies
- Provide companies with accessible websites

Return ONLY a JSON array with this exact structure (no additional text):
[
  {{
    "name": "Company Name",
    "domain": "example.com",
    "industry": "Industry",
    "reason": "Brief reason for similarity (one sentence)"
  }}
]"""

            print(f"[SIMILAR_LEADS] Calling Claude AI for discovery")

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            print(f"[SIMILAR_LEADS] AI response length: {len(response_text)}")

            # Parse JSON from response
            candidates = self._parse_json_response(response_text)

            # Validate and enrich domains
            validated_candidates = []
            for candidate in candidates:
                domain = candidate.get('domain', '').strip().lower()
                domain = domain.replace('http://', '').replace('https://', '').split('/')[0]

                if domain:
                    validated_candidates.append({
                        'name': candidate.get('name', ''),
                        'domain': domain,
                        'source': 'ai_discovery',
                        'confidence': 0.85,
                        'industry': candidate.get('industry', ''),
                        'reason': candidate.get('reason', '')
                    })

            return validated_candidates[:limit]

        except Exception as e:
            print(f"[SIMILAR_LEADS] Error in AI discovery: {type(e).__name__}: {e}")
            return []

    def _discover_from_google(self, reference_profile: Dict, criteria: Dict,
                             limit: int) -> List[Dict]:
        """
        Strategy 3: Use Google search to find similar companies

        Args:
            reference_profile: Reference company profile
            criteria: Similarity criteria
            limit: Max results to return

        Returns:
            List of candidate dictionaries
        """
        candidates = []

        # Build search queries based on criteria
        search_queries = []

        if criteria.get('industry') and reference_profile.get('industry'):
            search_queries.append(f"{reference_profile['industry']} companies")

        if criteria.get('business_model') and reference_profile.get('products_services'):
            products = reference_profile.get('products_services', [])[:2]
            if products:
                search_queries.append(f"{' '.join(products)} companies")

        # Limit to 2 search queries to avoid rate limits
        for query in search_queries[:2]:
            try:
                # Google search integration would go here
                # For now, we rely on cache and AI discovery
                pass

            except Exception as e:
                print(f"[SIMILAR_LEADS] Error in Google search: {e}")

        return candidates[:limit]

    def _score_similarity(self, reference_profile: Dict, candidate: Dict,
                         criteria: Dict) -> Dict:
        """
        Calculate similarity score using AI

        Args:
            reference_profile: Reference company profile
            criteria: Similarity criteria
            candidate: Candidate company to score

        Returns:
            Dictionary with similarity_score (0.0-1.0) and rationale
        """
        try:
            criteria_list = [k for k, v in criteria.items() if v]

            prompt = f"""Compare these two companies and provide a similarity score (0.0-1.0):

Reference Company:
- Name: {reference_profile['name']}
- Industry: {reference_profile['industry']}
- Size: {reference_profile['company_size']}
- Products: {', '.join(reference_profile.get('products_services', [])[:3])}

Candidate Company:
- Name: {candidate['name']}
- Domain: {candidate['domain']}
- Industry: {candidate.get('industry', 'Unknown')}

Evaluate similarity based on: {', '.join(criteria_list)}

Return ONLY a JSON object (no additional text):
{{
  "similarity_score": 0.85,
  "rationale": "Brief explanation of why these companies are similar (1-2 sentences)"
}}"""

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=512,
                temperature=0.3,  # Lower temperature for consistency
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            result = self._parse_json_response(response_text)

            if isinstance(result, dict):
                return {
                    'similarity_score': result.get('similarity_score', 0.5),
                    'rationale': result.get('rationale', 'Similar profile')
                }
            else:
                return {'similarity_score': 0.5, 'rationale': 'Unable to calculate'}

        except Exception as e:
            print(f"[SIMILAR_LEADS] Error scoring similarity: {e}")
            return {'similarity_score': 0.5, 'rationale': 'Error calculating similarity'}

    def _parse_json_response(self, response_text: str):
        """Parse JSON from Claude's response"""
        try:
            # Try to find JSON in response
            start = response_text.find('[')
            end = response_text.rfind(']') + 1

            if start != -1 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)

            # Try object notation
            start = response_text.find('{')
            end = response_text.rfind('}') + 1

            if start != -1 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[SIMILAR_LEADS] JSON parse error: {e}")

        return []

    def _create_leads_from_discoveries(self, discovery: SimilarLeadDiscovery,
                                      discoveries: List[Dict]):
        """
        Auto-create leads with AI Suggested status

        Args:
            discovery: SimilarLeadDiscovery instance
            discoveries: List of discovered company dictionaries
        """
        leads_created = 0

        for candidate in discoveries:
            try:
                # Check if lead/company already exists
                if self._check_existing_lead_or_company(candidate['domain'], discovery.tenant_id):
                    print(f"[SIMILAR_LEADS] Skipping {candidate['name']} - already exists")
                    continue

                # Create lead record
                lead = Lead(
                    tenant_id=discovery.tenant_id,
                    company_name=candidate['name'],
                    company_website=candidate['domain'],
                    lead_source='ai_suggested_similar',
                    status='new',
                    similar_to_company_id=discovery.reference_company_id,
                    similarity_score=candidate.get('similarity_score', 0.5),
                    similarity_rationale=candidate.get('similarity_rationale', candidate.get('reason', '')),
                    discovery_id=discovery.id,
                    owner_id=discovery.initiated_by_user_id,
                    description=f"AI-discovered lead similar to {discovery.reference_company_name}. {candidate.get('reason', '')}"
                )

                db.session.add(lead)
                leads_created += 1
                print(f"[SIMILAR_LEADS] Created lead: {candidate['name']}")

            except Exception as e:
                print(f"[SIMILAR_LEADS] Error creating lead for {candidate.get('name')}: {e}")
                continue

        discovery.leads_created = leads_created
        db.session.commit()

    def _check_existing_lead_or_company(self, domain: str, tenant_id: int) -> bool:
        """
        Check if lead or company already exists

        Args:
            domain: Company domain to check
            tenant_id: Tenant ID

        Returns:
            True if exists, False otherwise
        """
        if not domain:
            return False

        # Normalize domain
        domain = domain.lower().strip()

        # Check companies
        existing_company = Company.query.filter_by(
            tenant_id=tenant_id,
            website=domain
        ).first()

        if existing_company:
            return True

        # Check leads
        existing_lead = Lead.query.filter_by(
            tenant_id=tenant_id,
            company_website=domain
        ).first()

        if existing_lead:
            return True

        return False


# Singleton instance
similar_lead_discovery_service = SimilarLeadDiscoveryService()
