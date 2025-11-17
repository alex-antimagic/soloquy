"""
AI-Powered Website Generator Service
Uses business context to automatically generate websites
"""
import json
from typing import Dict, List, Optional
from anthropic import Anthropic
from flask import current_app
from app import db
from app.models.website import Website, WebsitePage, WebsiteTheme
from app.models.tenant import Tenant


class WebsiteGeneratorService:
    """Service for AI-powered website generation"""

    def __init__(self):
        self.client = Anthropic(api_key=current_app.config.get('ANTHROPIC_API_KEY'))

    def generate_website_for_tenant(self, tenant: Tenant, agent_id: Optional[int] = None) -> Website:
        """Generate a complete website for a tenant based on their business context"""

        # Get or create website
        website = Website.query.filter_by(tenant_id=tenant.id).first()
        if not website:
            website = Website(
                tenant_id=tenant.id,
                title=tenant.name,
                description=tenant.description
            )
            db.session.add(website)
            db.session.flush()

            # Create default theme
            theme = WebsiteTheme(website=website)
            db.session.add(theme)

        # Build context for AI
        business_context = tenant.business_context or {}
        custom_context = tenant.custom_context or ""

        # Generate theme colors based on industry
        theme_data = self._generate_theme(business_context, custom_context)
        self._apply_theme(website, theme_data)

        # Generate home page
        home_page = self._generate_home_page(tenant, website, business_context, custom_context, agent_id)

        # Generate about page
        about_page = self._generate_about_page(tenant, website, business_context, custom_context, agent_id)

        db.session.commit()

        return website

    def _generate_theme(self, business_context: Dict, custom_context: str) -> Dict:
        """Use AI to generate theme colors based on business context"""

        industry = business_context.get('industry', 'general')
        value_prop = business_context.get('value_proposition', '')

        prompt = f"""Based on this business information, suggest professional theme colors:

Industry: {industry}
Value Proposition: {value_prop}
Additional Context: {custom_context[:500] if custom_context else 'None'}

Generate a color scheme with:
- Primary color (brand color, eye-catching)
- Secondary color (complementary)
- Background color (light, readable)
- Text color (high contrast)

Return ONLY a JSON object with hex color codes:
{{
    "primary_color": "#hex",
    "secondary_color": "#hex",
    "background_color": "#hex",
    "text_color": "#hex",
    "heading_font": "Font Name",
    "body_font": "Font Name"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract JSON from response
            content = response.content[0].text
            # Try to find JSON in the response
            if '{' in content and '}' in content:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                json_str = content[json_start:json_end]
                return json.loads(json_str)
            else:
                return self._get_default_theme()
        except Exception as e:
            current_app.logger.error(f"Error generating theme: {e}")
            return self._get_default_theme()

    def _get_default_theme(self) -> Dict:
        """Get default theme colors"""
        return {
            "primary_color": "#667eea",
            "secondary_color": "#764ba2",
            "background_color": "#ffffff",
            "text_color": "#333333",
            "heading_font": "Inter",
            "body_font": "Inter"
        }

    def _apply_theme(self, website: Website, theme_data: Dict):
        """Apply theme data to website"""
        if not website.theme:
            theme = WebsiteTheme(website=website)
            db.session.add(theme)
        else:
            theme = website.theme

        theme.primary_color = theme_data.get('primary_color', '#667eea')
        theme.secondary_color = theme_data.get('secondary_color', '#764ba2')
        theme.background_color = theme_data.get('background_color', '#ffffff')
        theme.text_color = theme_data.get('text_color', '#333333')
        theme.heading_font = theme_data.get('heading_font', 'Inter')
        theme.body_font = theme_data.get('body_font', 'Inter')

    def _generate_home_page(self, tenant: Tenant, website: Website,
                           business_context: Dict, custom_context: str,
                           agent_id: Optional[int] = None) -> WebsitePage:
        """Generate home page content using AI"""

        # Check if home page already exists
        existing = WebsitePage.query.filter_by(
            website_id=website.id,
            page_type='home'
        ).first()

        if existing:
            return existing

        # Build AI prompt
        company_name = tenant.name
        description = business_context.get('company_description', tenant.description or '')
        products = business_context.get('products_services', '')
        value_prop = business_context.get('value_proposition', '')
        target_market = business_context.get('target_market', '')

        prompt = f"""Create homepage content for {company_name}.

Business Information:
- Description: {description}
- Products/Services: {products}
- Value Proposition: {value_prop}
- Target Market: {target_market}
- Additional Context: {custom_context[:500] if custom_context else 'None'}

Generate a JSON structure for a modern homepage with these sections:
1. Hero section (headline, subheadline, CTA)
2. Features section (3-4 key features)
3. About section (brief company story)
4. CTA section (call to action)

Return ONLY valid JSON in this exact format:
{{
    "sections": [
        {{
            "type": "hero",
            "heading": "Compelling headline",
            "subheading": "Supporting text",
            "cta_text": "Get Started",
            "cta_url": "/w/{tenant.slug}/contact"
        }},
        {{
            "type": "features",
            "features": [
                {{"icon": "rocket", "title": "Feature 1", "description": "Description"}},
                {{"icon": "shield", "title": "Feature 2", "description": "Description"}},
                {{"icon": "star", "title": "Feature 3", "description": "Description"}}
            ]
        }},
        {{
            "type": "text",
            "heading": "About Us",
            "content": "<p>Company story in HTML</p>"
        }},
        {{
            "type": "cta",
            "heading": "Ready to get started?",
            "subheading": "Join us today",
            "button_text": "Contact Us",
            "button_url": "/w/{tenant.slug}/contact"
        }}
    ]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract JSON
            content = response.content[0].text
            if '{' in content and '}' in content:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                json_str = content[json_start:json_end]
                content_json = json.loads(json_str)
            else:
                content_json = self._get_default_home_content(tenant)
        except Exception as e:
            current_app.logger.error(f"Error generating home page: {e}")
            content_json = self._get_default_home_content(tenant)

        # Create page
        page = WebsitePage(
            website_id=website.id,
            page_type='home',
            slug='',  # Home page has empty slug
            title=f'{tenant.name} - Home',
            meta_description=description[:160] if description else f'Welcome to {tenant.name}',
            content_json=content_json,
            is_published=False,  # Draft by default
            agent_id=agent_id
        )
        db.session.add(page)

        return page

    def _get_default_home_content(self, tenant: Tenant) -> Dict:
        """Get default home page content"""
        return {
            "sections": [
                {
                    "type": "hero",
                    "heading": f"Welcome to {tenant.name}",
                    "subheading": "We're here to help you succeed",
                    "cta_text": "Learn More",
                    "cta_url": f"/w/{tenant.slug}/about"
                },
                {
                    "type": "text",
                    "heading": "About Us",
                    "content": f"<p>{tenant.description or 'Your trusted partner for success.'}</p>"
                }
            ]
        }

    def _generate_about_page(self, tenant: Tenant, website: Website,
                            business_context: Dict, custom_context: str,
                            agent_id: Optional[int] = None) -> WebsitePage:
        """Generate about page"""

        # Check if exists
        existing = WebsitePage.query.filter_by(
            website_id=website.id,
            slug='about'
        ).first()

        if existing:
            return existing

        # Simple about page
        content = {
            "sections": [
                {
                    "type": "text",
                    "heading": f"About {tenant.name}",
                    "content": f"<p>{business_context.get('company_description', tenant.description or 'Learn more about our company.')}</p>"
                }
            ]
        }

        page = WebsitePage(
            website_id=website.id,
            page_type='custom',
            slug='about',
            title=f'About {tenant.name}',
            meta_description=f'Learn more about {tenant.name}',
            content_json=content,
            is_published=False,
            agent_id=agent_id
        )
        db.session.add(page)

        return page


# Singleton instance
website_generator = WebsiteGeneratorService()
