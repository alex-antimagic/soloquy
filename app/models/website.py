"""
Website builder models for multi-tenant website hosting
"""
from datetime import datetime
from app import db


class Website(db.Model):
    """Website configuration per tenant (1:1 relationship)"""
    __tablename__ = 'websites'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, unique=True, index=True)

    # Basic Info
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    logo_url = db.Column(db.String(500))  # Cloudinary URL
    favicon_url = db.Column(db.String(500))  # Cloudinary URL

    # Domain
    custom_domain = db.Column(db.String(255), unique=True, index=True)
    domain_verified = db.Column(db.Boolean, default=False, nullable=False)
    domain_verification_token = db.Column(db.String(100))
    domain_verified_at = db.Column(db.DateTime)

    # SEO
    default_og_image = db.Column(db.String(500))  # Default Open Graph image
    google_analytics_property_id = db.Column(db.String(50))  # GA4 property ID
    google_site_verification = db.Column(db.String(100))  # Meta tag for Search Console

    # Configuration
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    is_indexable = db.Column(db.Boolean, default=True, nullable=False)  # Allow search engines

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    published_at = db.Column(db.DateTime)

    # Relationships
    tenant = db.relationship('Tenant', back_populates='website')
    pages = db.relationship('WebsitePage', back_populates='website', lazy='dynamic', cascade='all, delete-orphan')
    theme = db.relationship('WebsiteTheme', back_populates='website', uselist=False, cascade='all, delete-orphan')
    forms = db.relationship('WebsiteForm', back_populates='website', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Website {self.title} (Tenant: {self.tenant_id})>'

    def get_public_url(self):
        """Get the public URL for this website"""
        if self.custom_domain and self.domain_verified:
            return f'https://{self.custom_domain}'
        # Fallback to tenant slug URL
        if self.tenant:
            return f'/website/{self.tenant.slug}'
        return None


class WebsitePage(db.Model):
    """Individual pages within a website"""
    __tablename__ = 'website_pages'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'), nullable=False, index=True)

    # Page Info
    page_type = db.Column(db.String(50), nullable=False)  # 'home', 'blog', 'landing', 'custom'
    slug = db.Column(db.String(200), nullable=False, index=True)  # URL path
    title = db.Column(db.String(200), nullable=False)

    # Content (JSON structure with sections/blocks)
    content_json = db.Column(db.JSON)  # Flexible page structure

    # SEO
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.Text)
    og_title = db.Column(db.String(200))
    og_description = db.Column(db.Text)
    og_image = db.Column(db.String(500))

    # Publishing
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    published_at = db.Column(db.DateTime)

    # Authorship
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))  # If AI-generated

    # Analytics
    view_count = db.Column(db.Integer, default=0, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    website = db.relationship('Website', back_populates='pages')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    agent = db.relationship('Agent', foreign_keys=[agent_id])

    # Unique constraint: slug must be unique per website
    __table_args__ = (
        db.UniqueConstraint('website_id', 'slug', name='unique_page_slug_per_website'),
    )

    def __repr__(self):
        return f'<WebsitePage {self.title} ({self.slug})>'

    def get_url(self):
        """Get the public URL for this page"""
        if self.website:
            base_url = self.website.get_public_url()
            if self.slug == 'home' or self.slug == '':
                return base_url
            return f'{base_url}/{self.slug}'
        return None


class WebsiteTheme(db.Model):
    """Theme/styling configuration per website"""
    __tablename__ = 'website_themes'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'), nullable=False, unique=True, index=True)

    # Theme Preset
    theme_name = db.Column(db.String(50), default='professional')  # 'professional', 'creative', 'minimal', etc.

    # Colors (Hex codes)
    primary_color = db.Column(db.String(7), default='#667eea')
    secondary_color = db.Column(db.String(7), default='#764ba2')
    background_color = db.Column(db.String(7), default='#ffffff')
    text_color = db.Column(db.String(7), default='#333333')
    accent_color = db.Column(db.String(7), default='#f6ad55')

    # Typography (Google Fonts)
    heading_font = db.Column(db.String(100), default='Inter')
    body_font = db.Column(db.String(100), default='Inter')

    # Layout Options
    header_style = db.Column(db.String(50), default='centered')  # 'centered', 'left-aligned', 'split'
    footer_style = db.Column(db.String(50), default='simple')  # 'simple', 'detailed'
    button_style = db.Column(db.String(50), default='rounded')  # 'rounded', 'sharp', 'pill'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    website = db.relationship('Website', back_populates='theme')

    def __repr__(self):
        return f'<WebsiteTheme {self.theme_name} (Website: {self.website_id})>'

    def get_css_variables(self):
        """Generate CSS variables for theme"""
        return f"""
        :root {{
            --primary-color: {self.primary_color};
            --secondary-color: {self.secondary_color};
            --background-color: {self.background_color};
            --text-color: {self.text_color};
            --accent-color: {self.accent_color};
            --heading-font: '{self.heading_font}', sans-serif;
            --body-font: '{self.body_font}', sans-serif;
        }}
        """


class WebsiteForm(db.Model):
    """Form builder for lead capture"""
    __tablename__ = 'website_forms'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'), nullable=False, index=True)

    # Form Info
    name = db.Column(db.String(200), nullable=False)
    form_key = db.Column(db.String(100), nullable=False, unique=True, index=True)  # URL-safe identifier
    description = db.Column(db.Text)

    # Form Fields (JSON array)
    fields = db.Column(db.JSON, nullable=False)  # [{"name": "email", "type": "email", "required": true, "label": "Email"}]

    # Submission Settings
    redirect_url = db.Column(db.String(500))  # Thank you page
    success_message = db.Column(db.Text, default='Thank you for your submission!')

    # Notifications
    notification_emails = db.Column(db.String(500))  # Comma-separated emails
    send_confirmation_email = db.Column(db.Boolean, default=False)
    confirmation_email_subject = db.Column(db.String(200))
    confirmation_email_body = db.Column(db.Text)

    # CRM Integration
    create_lead = db.Column(db.Boolean, default=True, nullable=False)  # Auto-create Lead in CRM
    create_contact = db.Column(db.Boolean, default=False)
    lead_source = db.Column(db.String(100), default='website_form')

    # Security
    require_captcha = db.Column(db.Boolean, default=True, nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    website = db.relationship('Website', back_populates='forms')
    submissions = db.relationship('FormSubmission', back_populates='form', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<WebsiteForm {self.name} ({self.form_key})>'


class FormSubmission(db.Model):
    """Track all form submissions"""
    __tablename__ = 'form_submissions'

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('website_forms.id'), nullable=False, index=True)

    # Submission Data
    data = db.Column(db.JSON, nullable=False)  # All form field values

    # Metadata
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    user_agent = db.Column(db.String(500))
    referrer = db.Column(db.String(500))

    # CRM Linkage
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))

    # Status
    is_spam = db.Column(db.Boolean, default=False)
    is_processed = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    form = db.relationship('WebsiteForm', back_populates='submissions')
    lead = db.relationship('Lead', foreign_keys=[lead_id])
    contact = db.relationship('Contact', foreign_keys=[contact_id])

    def __repr__(self):
        return f'<FormSubmission {self.id} (Form: {self.form_id})>'
