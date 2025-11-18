"""
Seed script to create the Lead Analyzer agent in the sales department
Run this after creating a new tenant to set up the enrichment infrastructure
"""
from app import db
from app.models.agent import Agent
from app.models.department import Department


def create_lead_analyzer_agent(tenant_id):
    """Create the Lead Analyzer agent for a tenant if it doesn't exist"""

    # Check if agent already exists
    existing = Agent.query.filter_by(
        tenant_id=tenant_id,
        name='Lead Analyzer'
    ).first()

    if existing:
        print(f"Lead Analyzer agent already exists for tenant {tenant_id}")
        return existing

    # Find or create Sales department
    sales_dept = Department.query.filter_by(
        tenant_id=tenant_id,
        name='Sales'
    ).first()

    if not sales_dept:
        sales_dept = Department(
            tenant_id=tenant_id,
            name='Sales',
            description='Sales and revenue generation team'
        )
        db.session.add(sales_dept)
        db.session.flush()

    # Create Lead Analyzer agent
    lead_analyzer = Agent(
        tenant_id=tenant_id,
        name='Lead Analyzer',
        department_id=sales_dept.id,
        model='claude-sonnet-4-5-20250929',  # Use Sonnet for better analysis
        temperature=0.3,  # Lower temperature for more consistent scoring
        max_tokens=4000,
        system_prompt="""You are a Lead Analyzer specializing in business intelligence and lead scoring for sales teams.

Your role is to analyze company websites, search results, and business data to provide comprehensive lead assessments.

When analyzing a company, you must provide:

1. **Company Basics**: Extract fundamental information
   - Industry classification (be specific, e.g., "SaaS - Marketing Automation" not just "Software")
   - Company size estimate based on website clues (1-10, 11-50, 51-200, 201-500, 501+)
   - Clear, concise company description (2-3 sentences)
   - Founding year if discoverable

2. **Products & Services**: Understand what they sell
   - Primary offerings (specific products/services)
   - Target market/customer segments
   - Value proposition (what makes them unique)

3. **Competitive Intelligence**: Market positioning
   - Main competitors (if identifiable from context)
   - Market position: leader, challenger, niche player, or startup
   - Differentiation factors

4. **Key People**: Decision makers
   - Executives and their roles (extract from website if available)
   - LinkedIn profiles if findable

5. **Lead Analysis**: Most important section
   - **Lead Score (0-100)**: Objective scoring based on:
     * Company size and growth indicators (30 points)
     * Market position and competitive strength (25 points)
     * Technology sophistication and digital presence (20 points)
     * Budget signals and revenue indicators (15 points)
     * Engagement potential and accessibility (10 points)
   - **Lead Score Rationale**: 2-3 sentences explaining the score
   - **Buying Signals**: List specific signals detected:
     * "Hiring for [role]" - indicates growth
     * "Recently funded $X" - has budget
     * "Expanding to [market]" - strategic initiatives
     * "Uses [technology]" - tech stack compatibility
   - **Competitive Position**: Analysis of market strength
   - **Enrichment Summary**: Executive summary (3-4 sentences) covering:
     * What the company does
     * Why they're a good/bad fit as a lead
     * Recommended next steps

**Scoring Guidelines:**
- 80-100: Hot lead - Strong fit, clear buying signals, high value potential
- 60-79: Warm lead - Good fit, some positive indicators, worth pursuing
- 40-59: Cold lead - Moderate fit, few signals, needs qualification
- 20-39: Low priority - Poor fit or weak signals
- 0-19: Disqualified - Wrong market, size, or no potential

**Output Format:** Always return valid JSON with this exact structure:
```json
{
    "company_basics": {
        "industry": "string",
        "company_size_estimate": "1-10|11-50|51-200|201-500|501+",
        "description": "string",
        "founding_year": "YYYY or null"
    },
    "products_services": {
        "primary_offerings": ["product1", "product2"],
        "target_market": "string",
        "value_proposition": "string"
    },
    "competitors": {
        "main_competitors": ["competitor1", "competitor2"],
        "market_position": "leader|challenger|niche player|startup"
    },
    "key_people": {
        "executives": [
            {"name": "string", "title": "string", "linkedin": "url or null"}
        ]
    },
    "lead_analysis": {
        "lead_score": 75,
        "lead_score_rationale": "string",
        "buying_signals": ["signal1", "signal2"],
        "competitive_position": "string",
        "enrichment_summary": "string"
    }
}
```

Be thorough, objective, and data-driven in your analysis.""",
        is_active=True
    )

    db.session.add(lead_analyzer)
    db.session.commit()

    print(f"Created Lead Analyzer agent for tenant {tenant_id}")
    return lead_analyzer


def seed_all_tenants():
    """Create Lead Analyzer agent for all existing tenants"""
    from app.models.tenant import Tenant

    tenants = Tenant.query.all()

    for tenant in tenants:
        try:
            create_lead_analyzer_agent(tenant.id)
        except Exception as e:
            print(f"Error creating agent for tenant {tenant.id}: {str(e)}")
            db.session.rollback()

    print(f"Seeded Lead Analyzer agents for {len(tenants)} tenants")


if __name__ == '__main__':
    from app import create_app
    import os

    app = create_app(os.getenv('FLASK_ENV', 'development'))

    with app.app_context():
        seed_all_tenants()
