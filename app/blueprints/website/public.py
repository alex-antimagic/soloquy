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
from app.models.status_page_config import StatusPageConfig
from app.models.status_component import StatusComponent
from app.models.status_incident import StatusIncident
from app.models.status_subscriber import StatusSubscriber
from datetime import datetime, timedelta
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


# ============================================================================
# STATUS PAGE PUBLIC ROUTES
# ============================================================================

@public_bp.route('/w/<tenant_slug>/status')
def status_page(tenant_slug):
    """Public status page - no authentication required"""
    # Find tenant
    tenant = Tenant.query.filter_by(slug=tenant_slug).first_or_404()
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()

    # Get status page config
    config = StatusPageConfig.query.filter_by(
        website_id=website.id,
        is_enabled=True
    ).first_or_404()

    # Get visible components
    components = StatusComponent.query.filter_by(
        config_id=config.id,
        is_visible=True
    ).order_by(StatusComponent.position).all()

    # Get active incidents
    active_incidents = StatusIncident.query.filter_by(
        config_id=config.id,
        is_published=True
    ).filter(StatusIncident.status != 'resolved').order_by(
        StatusIncident.created_at.desc()
    ).all()

    # Get recent resolved incidents
    history_cutoff = datetime.utcnow() - timedelta(days=config.show_incident_history_days)
    resolved_incidents = StatusIncident.query.filter_by(
        config_id=config.id,
        is_published=True,
        status='resolved'
    ).filter(
        StatusIncident.resolved_at >= history_cutoff
    ).order_by(StatusIncident.resolved_at.desc()).limit(10).all()

    # Calculate overall status
    overall_status = calculate_overall_status(components, active_incidents)

    return render_template('website/public/status_page.html',
                         website=website,
                         tenant=tenant,
                         config=config,
                         components=components,
                         active_incidents=active_incidents,
                         resolved_incidents=resolved_incidents,
                         overall_status=overall_status)


def calculate_overall_status(components, active_incidents):
    """
    Calculate overall system status
    Returns: 'operational', 'degraded', 'partial_outage', 'major_outage'
    """
    if not components:
        return 'operational'

    # Check for critical incidents
    critical_incidents = [i for i in active_incidents if i.severity == 'critical']
    if critical_incidents:
        return 'major_outage'

    # Count component statuses
    major_outage_count = sum(1 for c in components if c.status == 'major_outage')
    partial_outage_count = sum(1 for c in components if c.status == 'partial_outage')
    degraded_count = sum(1 for c in components if c.status == 'degraded_performance')

    total = len(components)

    # Determine overall status
    if major_outage_count > 0 or partial_outage_count > total / 2:
        return 'major_outage'
    elif partial_outage_count > 0 or degraded_count > total / 3:
        return 'partial_outage'
    elif degraded_count > 0:
        return 'degraded'
    else:
        return 'operational'


@public_bp.route('/w/<tenant_slug>/status/subscribe', methods=['POST'])
def status_subscribe(tenant_slug):
    """Subscribe to status updates - no authentication required"""
    tenant = Tenant.query.filter_by(slug=tenant_slug).first_or_404()
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    email = request.form.get('email', '').strip().lower()

    # Validation
    if not email or '@' not in email:
        flash('Please provide a valid email address.', 'error')
        return redirect(url_for('public_bp.status_page', tenant_slug=tenant_slug))

    # Rate limiting check (prevent spam)
    recent_subs = StatusSubscriber.query.filter_by(
        config_id=config.id,
        email=email
    ).filter(
        StatusSubscriber.created_at > datetime.utcnow() - timedelta(hours=1)
    ).count()

    if recent_subs > 3:
        flash('Too many subscription attempts. Please try again later.', 'error')
        return redirect(url_for('public_bp.status_page', tenant_slug=tenant_slug))

    # Check if already subscribed
    existing = StatusSubscriber.query.filter_by(
        config_id=config.id,
        email=email
    ).first()

    if existing and existing.confirmed:
        flash('You are already subscribed to status updates.', 'info')
        return redirect(url_for('public_bp.status_page', tenant_slug=tenant_slug))

    # Create or update subscriber
    if existing:
        subscriber = existing
        subscriber.is_active = True
    else:
        subscriber = StatusSubscriber(
            config_id=config.id,
            email=email
        )
        subscriber.generate_tokens()
        db.session.add(subscriber)

    db.session.commit()

    # Send confirmation email
    from app.services.status_notification_service import send_subscription_confirmation
    send_subscription_confirmation(subscriber, website, tenant)

    flash('Please check your email to confirm your subscription.', 'success')
    return redirect(url_for('public_bp.status_page', tenant_slug=tenant_slug))


@public_bp.route('/w/<tenant_slug>/status/confirm/<token>')
def confirm_subscription(tenant_slug, token):
    """Confirm email subscription"""
    tenant = Tenant.query.filter_by(slug=tenant_slug).first_or_404()
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()

    subscriber = StatusSubscriber.query.filter_by(confirmation_token=token).first_or_404()

    if subscriber.config.website_id != website.id:
        abort(404)

    subscriber.confirmed = True
    subscriber.confirmed_at = datetime.utcnow()
    db.session.commit()

    flash('Your subscription has been confirmed! You will receive status updates.', 'success')
    return redirect(url_for('public_bp.status_page', tenant_slug=tenant_slug))


@public_bp.route('/w/<tenant_slug>/status/unsubscribe/<token>')
def unsubscribe(tenant_slug, token):
    """Unsubscribe from status updates"""
    tenant = Tenant.query.filter_by(slug=tenant_slug).first_or_404()
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()

    subscriber = StatusSubscriber.query.filter_by(unsubscribe_token=token).first_or_404()

    if subscriber.config.website_id != website.id:
        abort(404)

    subscriber.is_active = False
    subscriber.unsubscribed_at = datetime.utcnow()
    db.session.commit()

    flash('You have been unsubscribed from status updates.', 'info')
    return redirect(url_for('public_bp.status_page', tenant_slug=tenant_slug))


@public_bp.route('/w/<tenant_slug>/status/incident/<int:incident_id>')
def incident_detail(tenant_slug, incident_id):
    """View incident detail page"""
    tenant = Tenant.query.filter_by(slug=tenant_slug).first_or_404()
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    incident = StatusIncident.query.filter_by(
        id=incident_id,
        config_id=config.id,
        is_published=True
    ).first_or_404()

    return render_template('website/public/incident_detail.html',
                         website=website,
                         tenant=tenant,
                         config=config,
                         incident=incident)
