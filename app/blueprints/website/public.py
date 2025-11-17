"""
Public Website Routes
Serves public-facing websites (no authentication required)
"""
from flask import render_template, redirect, url_for, flash, request, jsonify, abort
from app import db
from app.blueprints.website import public_bp
from app.models.website import Website, WebsitePage, WebsiteForm, FormSubmission
from app.models.tenant import Tenant
from app.models.lead import Lead
from app.models.contact import Contact
from datetime import datetime
import re


@public_bp.route('/w/<tenant_slug>')
@public_bp.route('/w/<tenant_slug>/')
def website_home(tenant_slug):
    """Serve public website home page"""
    # Find tenant by slug
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        abort(404)

    # Get website
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    if not website or not website.is_published:
        abort(404)

    # Get home page
    home_page = WebsitePage.query.filter_by(
        website_id=website.id,
        page_type='home',
        is_published=True
    ).first()

    if not home_page:
        # No home page, show placeholder
        return render_template('website/public/placeholder.html',
                             website=website,
                             tenant=tenant)

    # Increment view count
    home_page.view_count += 1
    db.session.commit()

    return render_template('website/public/page.html',
                         website=website,
                         page=home_page,
                         tenant=tenant)


@public_bp.route('/w/<tenant_slug>/<slug>')
def website_page(tenant_slug, slug):
    """Serve a specific page"""
    # Find tenant by slug
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        abort(404)

    # Get website
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    if not website or not website.is_published:
        abort(404)

    # Get page
    page = WebsitePage.query.filter_by(
        website_id=website.id,
        slug=slug,
        is_published=True
    ).first()

    if not page:
        abort(404)

    # Increment view count
    page.view_count += 1
    db.session.commit()

    return render_template('website/public/page.html',
                         website=website,
                         page=page,
                         tenant=tenant)


@public_bp.route('/w/<tenant_slug>/blog')
def blog_list(tenant_slug):
    """List all blog posts"""
    # Find tenant by slug
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        abort(404)

    # Get website
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    if not website or not website.is_published:
        abort(404)

    # Get all published blog posts
    posts = WebsitePage.query.filter_by(
        website_id=website.id,
        page_type='blog',
        is_published=True
    ).order_by(WebsitePage.published_at.desc()).all()

    return render_template('website/public/blog_list.html',
                         website=website,
                         posts=posts,
                         tenant=tenant)


@public_bp.route('/w/<tenant_slug>/blog/<slug>')
def blog_post(tenant_slug, slug):
    """View a blog post"""
    # Find tenant by slug
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        abort(404)

    # Get website
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    if not website or not website.is_published:
        abort(404)

    # Get blog post
    post = WebsitePage.query.filter_by(
        website_id=website.id,
        page_type='blog',
        slug=slug,
        is_published=True
    ).first()

    if not post:
        abort(404)

    # Increment view count
    post.view_count += 1
    db.session.commit()

    return render_template('website/public/blog_post.html',
                         website=website,
                         post=post,
                         tenant=tenant)


@public_bp.route('/w/<tenant_slug>/form/<form_key>', methods=['POST'])
def submit_form(tenant_slug, form_key):
    """Handle public form submissions"""
    # Find tenant by slug
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        return jsonify({'success': False, 'error': 'Website not found'}), 404

    # Get website
    website = Website.query.filter_by(tenant_id=tenant.id).first()
    if not website or not website.is_published:
        return jsonify({'success': False, 'error': 'Website not found'}), 404

    # Get form
    form = WebsiteForm.query.filter_by(
        website_id=website.id,
        form_key=form_key,
        is_active=True
    ).first()

    if not form:
        return jsonify({'success': False, 'error': 'Form not found'}), 404

    # Get form data
    data = request.get_json() or request.form.to_dict()

    # Basic spam check (honeypot field)
    if data.get('_honeypot'):
        return jsonify({'success': True, 'message': form.success_message})

    # Create form submission
    submission = FormSubmission(
        form_id=form.id,
        data=data,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        referrer=request.headers.get('Referer')
    )
    db.session.add(submission)

    # Create lead if enabled
    if form.create_lead:
        # Extract common fields
        email = data.get('email') or data.get('Email')
        name = data.get('name') or data.get('Name')
        phone = data.get('phone') or data.get('Phone')
        company = data.get('company') or data.get('Company')
        message = data.get('message') or data.get('Message')

        if email:
            # Split name into first/last if needed
            first_name = None
            last_name = None
            if name:
                name_parts = name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else None

            # Create lead
            lead = Lead(
                tenant_id=tenant.id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                company_name=company,
                lead_source=form.lead_source,
                notes=message or f'Submitted via website form: {form.name}',
                lead_status='new'
            )
            db.session.add(lead)
            db.session.flush()  # Get lead ID

            # Link to submission
            submission.lead_id = lead.id

    db.session.commit()

    # Return success response
    response = {
        'success': True,
        'message': form.success_message
    }

    if form.redirect_url:
        response['redirect_url'] = form.redirect_url

    return jsonify(response)
