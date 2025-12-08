"""
Competitive Analysis Service
Orchestrates full competitive analysis workflow
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from anthropic import Anthropic
from app import db
from app.models.competitive_analysis import CompetitiveAnalysis
from app.models.competitor_profile import CompetitorProfile
from app.models.website import Website
from app.services.business_intelligence_service import BusinessIntelligenceService


class CompetitiveAnalysisService:
    """Service for performing comprehensive competitive analysis"""

    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

        self.anthropic_client = Anthropic(api_key=api_key)
        self.bi_service = BusinessIntelligenceService()

    def create_analysis(self, website_id: int, competitor_ids: List[int],
                       analysis_type: str = 'comprehensive', agent_id: Optional[int] = None) -> CompetitiveAnalysis:
        """
        Create new analysis record and start processing

        Args:
            website_id: Website ID to analyze
            competitor_ids: List of CompetitorProfile IDs to compare against
            analysis_type: Type of analysis ('comprehensive', 'website', 'marketing')
            agent_id: Optional agent ID performing the analysis

        Returns:
            CompetitiveAnalysis instance with status='pending'
        """
        analysis = CompetitiveAnalysis(
            website_id=website_id,
            analysis_type=analysis_type,
            status='pending',
            competitor_ids=competitor_ids,
            competitor_count=len(competitor_ids),
            analyzed_by_agent_id=agent_id
        )

        db.session.add(analysis)
        db.session.commit()

        # Queue analysis as background job (analyzing multiple competitors takes 5-10 minutes)
        from app.tasks import run_competitive_analysis
        run_competitive_analysis.delay(analysis.id)

        return analysis

    def run_analysis(self, analysis_id: int):
        """
        Main analysis orchestration flow

        1. Fetch workspace website content
        2. For each competitor:
           a. Fetch website using BusinessIntelligenceService
           b. Extract key data
        3. Synthesize comparative analysis using Claude
        4. Store results
        5. Update status = 'completed'

        Args:
            analysis_id: ID of the CompetitiveAnalysis to run
        """
        analysis = CompetitiveAnalysis.query.get(analysis_id)
        if not analysis:
            return

        try:
            # Update status to processing
            analysis.status = 'processing'
            db.session.commit()

            # Step 1: Fetch workspace website data
            website = Website.query.get(analysis.website_id)
            if not website:
                raise ValueError("Website not found")

            workspace_data = self._fetch_workspace_data(website)

            # Step 2: Fetch competitor data
            competitors = CompetitorProfile.query.filter(
                CompetitorProfile.id.in_(analysis.competitor_ids)
            ).all()

            competitor_data_list = []
            for competitor in competitors:
                comp_data = self._fetch_competitor_data(competitor)
                if comp_data:
                    competitor_data_list.append(comp_data)

            if not competitor_data_list:
                raise ValueError("No competitor data could be fetched")

            # Step 3: Synthesize analysis with AI
            analysis_results = self._analyze_with_ai(workspace_data, competitor_data_list)

            # Step 4: Store results
            analysis.executive_summary = analysis_results.get('executive_summary')
            analysis.strengths = json.dumps(analysis_results.get('strengths', []))
            analysis.gaps = json.dumps(analysis_results.get('gaps', []))
            analysis.opportunities = json.dumps(analysis_results.get('opportunities', []))
            analysis.comparison_matrix = json.dumps(analysis_results.get('comparison_matrix', {}))
            analysis.detailed_findings = json.dumps(analysis_results.get('detailed_findings', []))

            # Step 5: Mark as completed
            analysis.status = 'completed'
            analysis.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            # Handle errors
            print(f"Error running analysis {analysis_id}: {e}")
            analysis.status = 'failed'
            analysis.executive_summary = f"Analysis failed: {str(e)}"
            db.session.commit()

    def _fetch_workspace_data(self, website: Website) -> Dict:
        """
        Fetch and parse workspace website data

        Args:
            website: Website instance

        Returns:
            Dictionary with workspace data
        """
        workspace_data = {
            'name': website.tenant.name,
            'website_title': website.title,
            'description': website.description,
            'url': website.get_public_url(),
            'content': None
        }

        # Try to fetch website content if published
        if website.is_published and website.tenant.website_url:
            try:
                html_content = self.bi_service._fetch_website_content(website.tenant.website_url)
                workspace_data['content'] = html_content[:50000]  # Limit to 50KB
            except Exception as e:
                print(f"Could not fetch workspace website content: {e}")

        # Add business context if available
        if website.tenant.business_context:
            try:
                business_context = json.loads(website.tenant.business_context)
                workspace_data.update({
                    'industry': business_context.get('industry'),
                    'products_services': business_context.get('products_services', []),
                    'target_market': business_context.get('target_market'),
                    'value_proposition': business_context.get('value_proposition'),
                    'company_description': business_context.get('company_description')
                })
            except (json.JSONDecodeError, ValueError):
                pass

        return workspace_data

    def _fetch_competitor_data(self, competitor: CompetitorProfile) -> Optional[Dict]:
        """
        Fetch and parse competitor website data

        Args:
            competitor: CompetitorProfile instance

        Returns:
            Dictionary with competitor data or None if fetch fails
        """
        try:
            # Construct full URL
            url = competitor.domain
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Fetch website content
            html_content = self.bi_service._fetch_website_content(url)

            # Parse basic info from HTML (simplified - could enhance with more parsing)
            return {
                'id': competitor.id,
                'name': competitor.company_name,
                'domain': competitor.domain,
                'industry': competitor.industry,
                'html_content': html_content[:50000],  # Limit to 50KB
                'url': url
            }

        except Exception as e:
            print(f"Error fetching data for {competitor.company_name}: {e}")
            return None

    def _analyze_with_ai(self, workspace_data: Dict, competitor_data_list: List[Dict]) -> Dict:
        """
        Use Claude to perform comparative analysis

        Args:
            workspace_data: Dictionary with workspace information
            competitor_data_list: List of dictionaries with competitor information

        Returns:
            Dictionary with analysis results (strengths, gaps, opportunities, etc.)
        """
        # Build comprehensive analysis prompt
        prompt = self._build_analysis_prompt(workspace_data, competitor_data_list)

        try:
            # Call Claude API for analysis
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response.content[0].text

            # Extract JSON from response
            analysis_results = self._parse_analysis_json(response_text)

            return analysis_results

        except Exception as e:
            print(f"Error analyzing with AI: {e}")
            return {
                'executive_summary': f"Analysis error: {str(e)}",
                'strengths': [],
                'gaps': [],
                'opportunities': [],
                'comparison_matrix': {},
                'detailed_findings': []
            }

    def _build_analysis_prompt(self, workspace_data: Dict, competitor_data_list: List[Dict]) -> str:
        """Build the Claude prompt for competitive analysis"""

        workspace_name = workspace_data.get('name', 'Your Company')
        workspace_desc = workspace_data.get('company_description', workspace_data.get('description', 'N/A'))
        workspace_industry = workspace_data.get('industry', 'N/A')
        workspace_products = ', '.join(workspace_data.get('products_services', [])[:5]) or 'N/A'
        workspace_value_prop = workspace_data.get('value_proposition', 'N/A')

        # Build competitor summaries
        competitor_summaries = []
        for idx, comp in enumerate(competitor_data_list, 1):
            summary = f"""
Competitor {idx}: {comp['name']}
- Domain: {comp['domain']}
- Industry: {comp.get('industry', 'Unknown')}
- Website Content: {comp.get('html_content', '')[:2000]}...
"""
            competitor_summaries.append(summary)

        competitors_str = '\n'.join(competitor_summaries)

        prompt = f"""Perform a comprehensive competitive analysis comparing {workspace_name} against {len(competitor_data_list)} competitors.

YOUR COMPANY:
- Name: {workspace_name}
- Industry: {workspace_industry}
- Description: {workspace_desc}
- Products/Services: {workspace_products}
- Value Proposition: {workspace_value_prop}

COMPETITORS:
{competitors_str}

Please analyze and provide a comprehensive competitive analysis with the following sections:

1. **Executive Summary** (2-3 sentences): High-level overview of your competitive position

2. **Strengths vs Competitors** (3-5 items): What does your company do better than competitors?
   For each strength, include:
   - title: Short name of strength
   - description: Detailed explanation
   - score: 1-10 rating

3. **Competitive Gaps** (3-5 items): What do competitors offer that you lack?
   For each gap, include:
   - title: Short name of gap
   - description: What's missing
   - benchmark: What competitors have (e.g., "3 out of 4 competitors offer...")
   - priority: "high", "medium", or "low"

4. **Strategic Opportunities** (3-5 items): Actionable recommendations
   For each opportunity, include:
   - title: Short name
   - priority: "high", "medium", or "low"
   - impact: Expected business impact
   - description: Detailed recommendation

5. **Comparison Matrix**: Key metrics compared side-by-side
   Include metrics like: number of products, pricing signals, content quality, etc.

Return your analysis as valid JSON with this structure:
{{
  "executive_summary": "...",
  "strengths": [
    {{"title": "...", "description": "...", "score": 8}}
  ],
  "gaps": [
    {{"title": "...", "description": "...", "benchmark": "...", "priority": "high"}}
  ],
  "opportunities": [
    {{"title": "...", "priority": "high", "impact": "...", "description": "..."}}
  ],
  "comparison_matrix": {{
    "metrics": [
      {{"name": "Product Count", "your_value": "5", "comp1_value": "8", "comp2_value": "12"}}
    ]
  }},
  "detailed_findings": [
    {{"competitor": "...", "key_insights": "...", "threats": "...", "opportunities": "..."}}
  ]
}}

IMPORTANT: Return ONLY valid JSON, no additional text or explanation."""

        return prompt

    def _parse_analysis_json(self, response_text: str) -> Dict:
        """Parse analysis JSON from Claude's response"""
        try:
            import re

            # Strip markdown code blocks if present
            # Claude sometimes wraps JSON in ```json ... ```
            response_text = response_text.strip()
            if response_text.startswith('```'):
                # Remove opening ``` or ```json
                response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
                # Remove closing ```
                response_text = re.sub(r'\n?```\s*$', '', response_text)

            # Try to find JSON object in response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1

            if start != -1 and end > start:
                json_str = response_text[start:end]

                # Try to fix common JSON issues
                # Remove trailing commas before closing braces/brackets
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

                analysis = json.loads(json_str)

                # Validate structure
                if isinstance(analysis, dict):
                    return analysis

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[COMPETITIVE_ANALYSIS] Error parsing analysis JSON: {e}")
            # Log first 500 chars of the response for debugging
            print(f"[COMPETITIVE_ANALYSIS] Response preview: {response_text[:500]}...")
            # Log the problematic JSON snippet around the error
            if hasattr(e, 'pos'):
                error_pos = e.pos
                snippet_start = max(0, error_pos - 100)
                snippet_end = min(len(json_str) if 'json_str' in locals() else len(response_text), error_pos + 100)
                problem_area = (json_str if 'json_str' in locals() else response_text)[snippet_start:snippet_end]
                print(f"[COMPETITIVE_ANALYSIS] Problem area: ...{problem_area}...")

        # Return default structure if parsing fails
        return {
            'executive_summary': "Analysis could not be completed due to parsing error.",
            'strengths': [],
            'gaps': [],
            'opportunities': [],
            'comparison_matrix': {},
            'detailed_findings': []
        }

    def get_latest_analysis(self, website_id: int) -> Optional[CompetitiveAnalysis]:
        """
        Get the most recent completed analysis for a website

        Args:
            website_id: Website ID

        Returns:
            CompetitiveAnalysis instance or None
        """
        return CompetitiveAnalysis.query.filter_by(
            website_id=website_id,
            status='completed'
        ).order_by(CompetitiveAnalysis.created_at.desc()).first()

    def get_analysis_by_id(self, analysis_id: int) -> Optional[CompetitiveAnalysis]:
        """Get analysis by ID"""
        return CompetitiveAnalysis.query.get(analysis_id)


# Singleton instance
competitive_analysis_service = CompetitiveAnalysisService()
