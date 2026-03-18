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
from app.models.department import Department
from app.models.status_page_config import StatusPageConfig
from app.models.status_component import StatusComponent
from app.models.status_incident import StatusIncident
from app.models.incident_update import IncidentUpdate
from app.models.status_subscriber import StatusSubscriber
from app.services.applet_manager import is_applet_enabled
from datetime import datetime
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

        # Auto-create status page config (enabled by default)
        status_config = StatusPageConfig(
            website_id=website.id,
            is_enabled=True,
            page_title='System Status',
            page_description=f'Current status of {tenant.name} services'
        )
        db.session.add(status_config)

        db.session.commit()

    # Get statistics
    total_pages = WebsitePage.query.filter_by(website_id=website.id).count()
    published_pages = WebsitePage.query.filter_by(website_id=website.id, is_published=True).count()
    total_forms = WebsiteForm.query.filter_by(website_id=website.id).count()
    total_submissions = FormSubmission.query.join(WebsiteForm).filter(WebsiteForm.website_id == website.id).count()

    # Get competitive analysis data
    from app.models.competitive_analysis import CompetitiveAnalysis
    from app.models.competitor_profile import CompetitorProfile
    import json

    latest_analysis = CompetitiveAnalysis.query.filter_by(
        website_id=website.id,
        status='completed'
    ).order_by(CompetitiveAnalysis.created_at.desc()).first()

    competitor_count = CompetitorProfile.query.filter_by(
        website_id=website.id,
        is_confirmed=True
    ).count()

    opportunity_count = 0
    if latest_analysis and latest_analysis.opportunities:
        try:
            opportunities = json.loads(latest_analysis.opportunities)
            opportunity_count = len(opportunities)
        except (json.JSONDecodeError, TypeError):
            pass

    return render_template('website/dashboard.html',
                         website=website,
                         total_pages=total_pages,
                         published_pages=published_pages,
                         total_forms=total_forms,
                         total_submissions=total_submissions,
                         latest_analysis=latest_analysis,
                         competitor_count=competitor_count,
                         opportunity_count=opportunity_count)


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


# =============================================================================
# COMPETITIVE ANALYSIS ROUTES
# =============================================================================

@website_bp.route('/competitors')
@login_required
def competitors():
    """Competitor management page"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Please set up your website first.', 'warning')
        return redirect(url_for('website.dashboard'))

    from app.models.competitor_profile import CompetitorProfile

    # Get all competitors for this website
    all_competitors = CompetitorProfile.query.filter_by(website_id=website.id).all()

    # Separate confirmed vs suggested
    confirmed = [c for c in all_competitors if c.is_confirmed]
    suggested = [c for c in all_competitors if not c.is_confirmed]

    return render_template('website/competitors.html',
                         website=website,
                         confirmed_competitors=confirmed,
                         suggested_competitors=suggested)


@website_bp.route('/competitors/suggest', methods=['POST'])
@login_required
def suggest_competitors():
    """API endpoint to trigger AI competitor suggestion"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        return jsonify({"success": False, "error": "No website found"}), 404

    from app.services.competitor_identification_service import competitor_identification_service
    from app.models.competitor_profile import CompetitorProfile

    try:
        suggestions = competitor_identification_service.suggest_competitors(
            tenant_id=tenant.id,
            limit=10
        )

        # Create CompetitorProfile records for suggestions
        created_count = 0
        for suggestion in suggestions:
            existing = CompetitorProfile.query.filter_by(
                website_id=website.id,
                domain=suggestion['website']
            ).first()

            if not existing:
                competitor = CompetitorProfile(
                    website_id=website.id,
                    company_name=suggestion['name'],
                    domain=suggestion['website'],
                    is_confirmed=False,
                    suggested_by_agent=True,
                    confidence_score=suggestion.get('confidence', 0.8),
                    source=suggestion.get('source', 'ai_suggested'),
                    created_by_id=current_user.id
                )
                db.session.add(competitor)
                created_count += 1

        db.session.commit()

        if len(suggestions) > 0:
            flash(f'Found {len(suggestions)} potential competitors!', 'success')
        else:
            # Provide specific guidance on what's missing
            missing_context = []
            if not tenant.business_context:
                missing_context.append('business description')
            if not tenant.custom_context:
                missing_context.append('workspace context')
            if not tenant.website_url:
                missing_context.append('website URL')

            if missing_context:
                flash(f'No competitors found. To get AI suggestions, please add: {", ".join(missing_context)}. '
                      f'Go to Settings to update your workspace information.', 'warning')
            else:
                flash('No competitors found. Try adding more details about your business, products, or industry.', 'info')

        return redirect(url_for('website.competitors'))

    except Exception as e:
        flash(f'Error generating suggestions: {str(e)}', 'danger')
        return redirect(url_for('website.competitors'))


@website_bp.route('/competitors/<int:competitor_id>/confirm', methods=['POST'])
@login_required
def confirm_competitor(competitor_id):
    """Confirm a suggested competitor"""
    from app.models.competitor_profile import CompetitorProfile

    competitor = CompetitorProfile.query.get_or_404(competitor_id)

    # Ensure user has access to this website
    if competitor.website.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('website.competitors'))

    competitor.is_confirmed = True
    db.session.commit()

    flash(f'{competitor.company_name} confirmed as competitor.', 'success')
    return redirect(url_for('website.competitors'))


@website_bp.route('/competitors/<int:competitor_id>/remove', methods=['POST'])
@login_required
def remove_competitor(competitor_id):
    """Remove a competitor"""
    from app.models.competitor_profile import CompetitorProfile

    competitor = CompetitorProfile.query.get_or_404(competitor_id)

    # Ensure user has access to this website
    if competitor.website.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('website.competitors'))

    company_name = competitor.company_name
    db.session.delete(competitor)
    db.session.commit()

    flash(f'{company_name} removed from competitors.', 'success')
    return redirect(url_for('website.competitors'))


@website_bp.route('/competitors/add', methods=['POST'])
@login_required
def add_competitor():
    """Add competitor manually"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('No website found.', 'danger')
        return redirect(url_for('website.dashboard'))

    from app.models.competitor_profile import CompetitorProfile

    company_name = request.form.get('company_name', '').strip()
    domain = request.form.get('domain', '').strip()
    industry = request.form.get('industry', '').strip()
    notes = request.form.get('notes', '').strip()

    if not company_name or not domain:
        flash('Company name and domain are required.', 'danger')
        return redirect(url_for('website.competitors'))

    # Check if already exists
    existing = CompetitorProfile.query.filter_by(
        website_id=website.id,
        domain=domain
    ).first()

    if existing:
        flash(f'{company_name} is already in your competitor list.', 'warning')
        return redirect(url_for('website.competitors'))

    competitor = CompetitorProfile(
        website_id=website.id,
        company_name=company_name,
        domain=domain,
        industry=industry,
        notes=notes,
        is_confirmed=True,
        suggested_by_agent=False,
        source='manual',
        created_by_id=current_user.id
    )

    db.session.add(competitor)
    db.session.commit()

    flash(f'{company_name} added successfully!', 'success')
    return redirect(url_for('website.competitors'))


@website_bp.route('/analysis/start', methods=['POST'])
@login_required
def start_analysis():
    """Trigger new competitive analysis"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('No website found.', 'danger')
        return redirect(url_for('website.dashboard'))

    from app.services.competitive_analysis_service import competitive_analysis_service
    from app.models.agent import Agent

    competitor_ids = request.form.getlist('competitor_ids[]')

    if not competitor_ids:
        flash('Please select at least one competitor to analyze.', 'warning')
        return redirect(url_for('website.competitors'))

    # Convert to integers
    competitor_ids = [int(id) for id in competitor_ids]

    # Get Maya agent (or first agent with competitive analysis enabled)
    maya = Agent.query.join(Agent.department).filter(
        Agent.department.has(tenant_id=tenant.id),
        Agent.enable_competitive_analysis == True
    ).first()

    try:
        analysis = competitive_analysis_service.create_analysis(
            website_id=website.id,
            competitor_ids=competitor_ids,
            analysis_type='comprehensive',
            agent_id=maya.id if maya else None
        )

        if analysis.status == 'completed':
            flash('Competitive analysis completed!', 'success')
            return redirect(url_for('website.view_analysis', analysis_id=analysis.id))
        elif analysis.status == 'failed':
            flash(f'Analysis failed: {analysis.executive_summary}', 'danger')
            return redirect(url_for('website.competitors'))
        else:
            flash('Competitive analysis started. This may take a few minutes.', 'info')
            return redirect(url_for('website.analysis_progress', analysis_id=analysis.id))

    except Exception as e:
        flash(f'Error starting analysis: {str(e)}', 'danger')
        return redirect(url_for('website.competitors'))


@website_bp.route('/analysis/<int:analysis_id>')
@login_required
def view_analysis(analysis_id):
    """View completed analysis results"""
    from app.models.competitive_analysis import CompetitiveAnalysis
    from app.models.competitor_profile import CompetitorProfile
    from app.models.agent import Agent
    import json

    analysis = CompetitiveAnalysis.query.get_or_404(analysis_id)

    # Ensure user has access to this analysis
    if analysis.website.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('website.dashboard'))

    # Get competitor details
    competitors = CompetitorProfile.query.filter(
        CompetitorProfile.id.in_(analysis.competitor_ids or [])
    ).all()

    # Parse JSON fields
    strengths = json.loads(analysis.strengths) if analysis.strengths else []
    gaps = json.loads(analysis.gaps) if analysis.gaps else []
    opportunities = json.loads(analysis.opportunities) if analysis.opportunities else []
    comparison_matrix = json.loads(analysis.comparison_matrix) if analysis.comparison_matrix else {}

    # Find Maya agent (or the agent who performed this analysis) for chat links
    maya_agent = None
    if analysis.analyzed_by_agent_id:
        maya_agent = Agent.query.get(analysis.analyzed_by_agent_id)
    else:
        # Fallback: find any agent with competitive analysis enabled
        maya_agent = Agent.query.join(Agent.department).filter(
            Department.tenant_id == g.current_tenant.id,
            Agent.enable_competitive_analysis == True
        ).first()

    return render_template('website/analysis_view.html',
                         analysis=analysis,
                         competitors=competitors,
                         strengths=strengths,
                         gaps=gaps,
                         opportunities=opportunities,
                         comparison_matrix=comparison_matrix,
                         maya_agent=maya_agent)


@website_bp.route('/analysis/<int:analysis_id>/progress')
@login_required
def analysis_progress(analysis_id):
    """Show analysis progress (polling page)"""
    from app.models.competitive_analysis import CompetitiveAnalysis

    analysis = CompetitiveAnalysis.query.get_or_404(analysis_id)

    # Ensure user has access to this analysis
    if analysis.website.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('website.dashboard'))

    if analysis.status == 'completed':
        return redirect(url_for('website.view_analysis', analysis_id=analysis.id))

    return render_template('website/analysis_progress.html', analysis=analysis)


# =============================================================================
# STATUS PAGE ADMIN ROUTES
# =============================================================================

@website_bp.route('/status')
@login_required
def status_dashboard():
    """Status page admin dashboard"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first()

    if not website:
        flash('Please set up your website first.', 'warning')
        return redirect(url_for('website.dashboard'))

    # Get or create status page config
    config = StatusPageConfig.query.filter_by(website_id=website.id).first()
    if not config:
        config = StatusPageConfig(
            website_id=website.id,
            page_title='System Status',
            page_description=f'Current status of {tenant.name} services'
        )
        db.session.add(config)
        db.session.commit()

    # Get statistics
    total_components = StatusComponent.query.filter_by(config_id=config.id).count()
    active_incidents = StatusIncident.query.filter_by(
        config_id=config.id
    ).filter(StatusIncident.status != 'resolved').count()
    total_subscribers = StatusSubscriber.query.filter_by(
        config_id=config.id,
        confirmed=True,
        is_active=True
    ).count()

    # Get recent incidents
    recent_incidents = StatusIncident.query.filter_by(
        config_id=config.id
    ).order_by(StatusIncident.created_at.desc()).limit(10).all()

    return render_template('website/status/dashboard.html',
                         website=website,
                         config=config,
                         total_components=total_components,
                         active_incidents=active_incidents,
                         total_subscribers=total_subscribers,
                         recent_incidents=recent_incidents)


@website_bp.route('/status/settings', methods=['GET', 'POST'])
@login_required
def status_settings():
    """Configure status page settings"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    if request.method == 'POST':
        config.is_enabled = request.form.get('is_enabled') == 'on'
        config.page_title = request.form.get('page_title', '').strip()
        config.page_description = request.form.get('page_description', '').strip()
        config.support_url = request.form.get('support_url', '').strip() or None
        config.show_incident_history_days = int(request.form.get('show_incident_history_days', 90))

        db.session.commit()
        flash('Status page settings updated successfully!', 'success')
        return redirect(url_for('website.status_settings'))

    return render_template('website/status/settings.html',
                         website=website,
                         config=config)


@website_bp.route('/status/components')
@login_required
def status_components():
    """Manage system components"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    components = StatusComponent.query.filter_by(
        config_id=config.id
    ).order_by(StatusComponent.position).all()

    return render_template('website/status/components.html',
                         website=website,
                         config=config,
                         components=components)


@website_bp.route('/status/components/create', methods=['POST'])
@login_required
def create_component():
    """Create a new component"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Component name is required.', 'error')
        return redirect(url_for('website.status_components'))

    # Get max position
    max_pos = db.session.query(db.func.max(StatusComponent.position)).filter_by(
        config_id=config.id
    ).scalar() or 0

    component = StatusComponent(
        config_id=config.id,
        name=name,
        description=description,
        position=max_pos + 1,
        status='operational'
    )

    db.session.add(component)
    db.session.commit()

    flash(f'Component "{name}" created successfully!', 'success')
    return redirect(url_for('website.status_components'))


@website_bp.route('/status/components/<int:component_id>/update-status', methods=['POST'])
@login_required
def update_component_status(component_id):
    """Update component status (AJAX endpoint)"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    component = StatusComponent.query.filter_by(
        id=component_id,
        config_id=config.id
    ).first_or_404()

    new_status = request.form.get('status')
    if new_status not in ['operational', 'degraded_performance', 'partial_outage', 'major_outage']:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400

    component.update_status(new_status)
    db.session.commit()

    return jsonify({'success': True, 'component': component.name, 'status': new_status})


@website_bp.route('/status/incidents')
@login_required
def status_incidents():
    """View all incidents"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    # Filter by status if provided
    status_filter = request.args.get('status', 'all')

    query = StatusIncident.query.filter_by(config_id=config.id)

    if status_filter != 'all':
        if status_filter == 'active':
            query = query.filter(StatusIncident.status != 'resolved')
        else:
            query = query.filter_by(status=status_filter)

    incidents = query.order_by(StatusIncident.created_at.desc()).all()

    return render_template('website/status/incidents.html',
                         website=website,
                         config=config,
                         incidents=incidents,
                         status_filter=status_filter)


@website_bp.route('/status/incidents/create', methods=['GET', 'POST'])
@login_required
def create_incident():
    """Create a new incident"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    components = StatusComponent.query.filter_by(config_id=config.id).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        initial_message = request.form.get('initial_message', '').strip()
        severity = request.form.get('severity', 'minor')
        affected_ids = request.form.getlist('affected_components')
        is_published = request.form.get('is_published') == 'on'
        notify = request.form.get('notify_subscribers') == 'on'

        if not title or not initial_message:
            flash('Title and initial message are required.', 'error')
            return redirect(url_for('website.create_incident'))

        # Create incident
        incident = StatusIncident(
            config_id=config.id,
            title=title,
            severity=severity,
            status='investigating',
            affected_component_ids=[int(id) for id in affected_ids if id],
            created_by_id=current_user.id,
            is_published=is_published
        )
        db.session.add(incident)
        db.session.flush()  # Get incident ID

        # Create initial update
        update = IncidentUpdate(
            incident_id=incident.id,
            message=initial_message,
            update_type='investigating',
            created_by_id=current_user.id,
            notify_subscribers=notify
        )
        db.session.add(update)
        db.session.commit()

        # Send notifications if requested
        if notify and is_published:
            from app.services.status_notification_service import send_incident_notification
            send_incident_notification(incident, update, 'created')

        flash('Incident created successfully!', 'success')
        return redirect(url_for('website.view_incident', incident_id=incident.id))

    return render_template('website/status/create_incident.html',
                         website=website,
                         config=config,
                         components=components)


@website_bp.route('/status/incidents/<int:incident_id>')
@login_required
def view_incident(incident_id):
    """View incident details"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    incident = StatusIncident.query.filter_by(
        id=incident_id,
        config_id=config.id
    ).first_or_404()

    return render_template('website/status/incident_detail.html',
                         website=website,
                         config=config,
                         incident=incident)


@website_bp.route('/status/incidents/<int:incident_id>/update', methods=['POST'])
@login_required
def add_incident_update(incident_id):
    """Add update to existing incident"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    incident = StatusIncident.query.filter_by(
        id=incident_id,
        config_id=config.id
    ).first_or_404()

    message = request.form.get('message', '').strip()
    update_type = request.form.get('update_type', 'update')
    notify = request.form.get('notify_subscribers') == 'on'

    if not message:
        flash('Update message is required.', 'error')
        return redirect(url_for('website.view_incident', incident_id=incident_id))

    # Create update
    update = IncidentUpdate(
        incident_id=incident.id,
        message=message,
        update_type=update_type,
        created_by_id=current_user.id,
        notify_subscribers=notify
    )
    db.session.add(update)

    # Update incident status if changing
    if update_type in ['investigating', 'identified', 'monitoring', 'resolved']:
        incident.status = update_type
        if update_type == 'resolved':
            incident.resolved_at = datetime.utcnow()

    db.session.commit()

    # Send notifications if requested
    if notify and incident.is_published:
        from app.services.status_notification_service import send_incident_notification
        send_incident_notification(incident, update, 'updated')

    flash('Incident update added successfully!', 'success')
    return redirect(url_for('website.view_incident', incident_id=incident_id))


@website_bp.route('/status/subscribers')
@login_required
def status_subscribers():
    """View and manage subscribers"""
    tenant = g.current_tenant
    website = Website.query.filter_by(tenant_id=tenant.id).first_or_404()
    config = StatusPageConfig.query.filter_by(website_id=website.id).first_or_404()

    # Get active subscribers
    active_subscribers = StatusSubscriber.query.filter_by(
        config_id=config.id,
        confirmed=True,
        is_active=True
    ).order_by(StatusSubscriber.confirmed_at.desc()).all()

    # Get pending confirmations
    pending = StatusSubscriber.query.filter_by(
        config_id=config.id,
        confirmed=False,
        is_active=True
    ).order_by(StatusSubscriber.created_at.desc()).all()

    return render_template('website/status/subscribers.html',
                         website=website,
                         config=config,
                         active_subscribers=active_subscribers,
                         pending=pending)
