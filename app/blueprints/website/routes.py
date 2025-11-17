"""
Website Builder Admin Routes
Requires authentication and admin permissions
"""
from flask import render_template, redirect, url_for, flash, request, jsonify, g
from flask_login import login_required, current_user
from app import db
from app.blueprints.website import website_bp
from app.blueprints.website.forms import WebsiteSettingsForm, WebsitePageForm, WebsiteThemeForm, WebsiteFormBuilderForm
from app.models.website import Website, WebsitePage, WebsiteTheme, WebsiteForm, FormSubmission
from app.models.workspace_applet import WorkspaceApplet
from app.services.applet_manager import is_applet_enabled
import secrets


@website_bp.before_request
@login_required
def check_access():
    """Ensure user has access to website builder"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Check if website applet is enabled
    if not is_applet_enabled(g.current_tenant.id, 'website'):
        flash('Website Builder is not enabled for this workspace.', 'warning')
        return redirect(url_for('tenant.home'))


@website_bp.route('/')
@login_required
def dashboard():
    """Website builder dashboard"""
    tenant = g.current_tenant

    # Get or create website for this tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        # Create default website
        website = Website(
            tenant_id=tenant.id,
            title=tenant.name,
            description=tenant.description
        )
        db.session.add(website)

        # Create default theme
        theme = WebsiteTheme(website=website)
        db.session.add(theme)

        db.session.commit()

    # Get statistics
    total_pages = WebsitePage.query.filter_by(website_id=website.id).count()
    published_pages = WebsitePage.query.filter_by(website_id=website.id, is_published=True).count()
    total_forms = WebsiteForm.query.filter_by(website_id=website.id).count()
    total_submissions = FormSubmission.query.join(WebsiteForm).filter(WebsiteForm.website_id == website.id).count()

    return render_template('website/dashboard.html',
                         website=website,
                         total_pages=total_pages,
                         published_pages=published_pages,
                         total_forms=total_forms,
                         total_submissions=total_submissions)


@website_bp.route('/pages')
@login_required
def pages():
    """List all pages"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Website not found.', 'error')
        return redirect(url_for('website.dashboard'))

    pages = WebsitePage.query.filter_by(website_id=website.id).order_by(WebsitePage.created_at.desc()).all()

    return render_template('website/pages/index.html', website=website, pages=pages)


@website_bp.route('/pages/create', methods=['GET', 'POST'])
@login_required
def create_page():
    """Create a new page"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Website not found.', 'error')
        return redirect(url_for('website.dashboard'))

    form = WebsitePageForm()

    if form.validate_on_submit():
        # Check if slug already exists
        existing = WebsitePage.query.filter_by(website_id=website.id, slug=form.slug.data).first()
        if existing:
            flash(f'A page with slug "{form.slug.data}" already exists.', 'error')
            return render_template('website/pages/create.html', form=form, website=website)

        # Create page
        page = WebsitePage(
            website_id=website.id,
            page_type=form.page_type.data,
            slug=form.slug.data,
            title=form.title.data,
            meta_description=form.meta_description.data,
            is_published=form.is_published.data,
            created_by_id=current_user.id,
            content_json={'sections': []}  # Empty page initially
        )

        db.session.add(page)
        db.session.commit()

        flash(f'Page "{page.title}" created successfully!', 'success')
        return redirect(url_for('website.edit_page', page_id=page.id))

    return render_template('website/pages/create.html', form=form, website=website)


@website_bp.route('/pages/<int:page_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_page(page_id):
    """Edit a page"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    page = WebsitePage.query.filter_by(id=page_id, website_id=website.id).first_or_404()

    form = WebsitePageForm(obj=page)

    if form.validate_on_submit():
        # Check slug uniqueness (excluding current page)
        existing = WebsitePage.query.filter(
            WebsitePage.website_id == website.id,
            WebsitePage.slug == form.slug.data,
            WebsitePage.id != page.id
        ).first()
        if existing:
            flash(f'A page with slug "{form.slug.data}" already exists.', 'error')
            return render_template('website/pages/edit.html', form=form, page=page, website=website)

        page.page_type = form.page_type.data
        page.slug = form.slug.data
        page.title = form.title.data
        page.meta_description = form.meta_description.data
        page.is_published = form.is_published.data

        db.session.commit()

        flash(f'Page "{page.title}" updated successfully!', 'success')
        return redirect(url_for('website.pages'))

    return render_template('website/pages/edit.html', form=form, page=page, website=website)


@website_bp.route('/pages/<int:page_id>/delete', methods=['POST'])
@login_required
def delete_page(page_id):
    """Delete a page"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    page = WebsitePage.query.filter_by(id=page_id, website_id=website.id).first_or_404()

    title = page.title
    db.session.delete(page)
    db.session.commit()

    flash(f'Page "{title}" deleted successfully!', 'success')
    return redirect(url_for('website.pages'))


@website_bp.route('/theme', methods=['GET', 'POST'])
@login_required
def theme():
    """Edit website theme"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website or not website.theme:
        flash('Website or theme not found.', 'error')
        return redirect(url_for('website.dashboard'))

    form = WebsiteThemeForm(obj=website.theme)

    if form.validate_on_submit():
        website.theme.theme_name = form.theme_name.data
        website.theme.primary_color = form.primary_color.data
        website.theme.secondary_color = form.secondary_color.data
        website.theme.background_color = form.background_color.data
        website.theme.text_color = form.text_color.data
        website.theme.heading_font = form.heading_font.data
        website.theme.body_font = form.body_font.data

        db.session.commit()

        flash('Theme updated successfully!', 'success')
        return redirect(url_for('website.theme'))

    return render_template('website/theme/edit.html', form=form, website=website)


@website_bp.route('/forms')
@login_required
def forms():
    """List all forms"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Website not found.', 'error')
        return redirect(url_for('website.dashboard'))

    forms = WebsiteForm.query.filter_by(website_id=website.id).order_by(WebsiteForm.created_at.desc()).all()

    return render_template('website/forms/index.html', website=website, forms=forms)


@website_bp.route('/forms/create', methods=['GET', 'POST'])
@login_required
def create_form():
    """Create a new form"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Website not found.', 'error')
        return redirect(url_for('website.dashboard'))

    form = WebsiteFormBuilderForm()

    if form.validate_on_submit():
        # Check if form_key already exists
        existing = WebsiteForm.query.filter_by(form_key=form.form_key.data).first()
        if existing:
            flash(f'A form with key "{form.form_key.data}" already exists.', 'error')
            return render_template('website/forms/create.html', form=form, website=website)

        # Create form with default fields
        web_form = WebsiteForm(
            website_id=website.id,
            name=form.name.data,
            form_key=form.form_key.data,
            description=form.description.data,
            success_message=form.success_message.data,
            redirect_url=form.redirect_url.data,
            notification_emails=form.notification_emails.data,
            create_lead=form.create_lead.data,
            require_captcha=form.require_captcha.data,
            is_active=form.is_active.data,
            fields=[
                {'name': 'name', 'type': 'text', 'label': 'Name', 'required': True},
                {'name': 'email', 'type': 'email', 'label': 'Email', 'required': True},
                {'name': 'message', 'type': 'textarea', 'label': 'Message', 'required': True}
            ]
        )

        db.session.add(web_form)
        db.session.commit()

        flash(f'Form "{web_form.name}" created successfully!', 'success')
        return redirect(url_for('website.edit_form', form_id=web_form.id))

    return render_template('website/forms/create.html', form=form, website=website)


@website_bp.route('/forms/<int:form_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_form(form_id):
    """Edit a form"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    web_form = WebsiteForm.query.filter_by(id=form_id, website_id=website.id).first_or_404()

    form = WebsiteFormBuilderForm(obj=web_form)

    if form.validate_on_submit():
        web_form.name = form.name.data
        web_form.description = form.description.data
        web_form.success_message = form.success_message.data
        web_form.redirect_url = form.redirect_url.data
        web_form.notification_emails = form.notification_emails.data
        web_form.create_lead = form.create_lead.data
        web_form.require_captcha = form.require_captcha.data
        web_form.is_active = form.is_active.data

        db.session.commit()

        flash(f'Form "{web_form.name}" updated successfully!', 'success')
        return redirect(url_for('website.forms'))

    return render_template('website/forms/edit.html', form=form, web_form=web_form, website=website)


@website_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Website settings"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Website not found.', 'error')
        return redirect(url_for('website.dashboard'))

    form = WebsiteSettingsForm(obj=website)

    if form.validate_on_submit():
        website.title = form.title.data
        website.description = form.description.data
        website.is_published = form.is_published.data
        website.is_indexable = form.is_indexable.data
        website.google_analytics_property_id = form.google_analytics_property_id.data

        db.session.commit()

        flash('Settings updated successfully!', 'success')
        return redirect(url_for('website.settings'))

    return render_template('website/settings.html', form=form, website=website)
