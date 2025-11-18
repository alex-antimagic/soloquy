from flask import render_template, request, jsonify, g, make_response
from flask_login import login_required, current_user
from app.blueprints.crm import crm_bp
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.deal_pipeline import DealPipeline
from app.models.deal_stage import DealStage
from app.models.activity import Activity
from app.models.lead import Lead
from app.services.default_crm_data import create_default_deal_pipeline
from app.services.csv_import_service import CSVImportService
from app import db
from datetime import datetime


@crm_bp.route('/')
@login_required
def index():
    """CRM Dashboard"""
    # Get aggregate metrics
    total_companies = Company.query.filter_by(tenant_id=g.current_tenant.id).count()
    total_contacts = Contact.query.filter_by(tenant_id=g.current_tenant.id).count()
    total_deals = Deal.query.filter_by(tenant_id=g.current_tenant.id, status='open').count()

    # Get deal value
    deal_value_result = db.session.query(db.func.sum(Deal.amount)).filter_by(
        tenant_id=g.current_tenant.id,
        status='open'
    ).scalar()
    total_deal_value = float(deal_value_result) if deal_value_result else 0

    # Get recent activities
    recent_activities = Activity.query.filter_by(
        tenant_id=g.current_tenant.id
    ).order_by(Activity.created_at.desc()).limit(10).all()

    return render_template('crm/index.html',
                          title='CRM Dashboard',
                          total_companies=total_companies,
                          total_contacts=total_contacts,
                          total_deals=total_deals,
                          total_deal_value=total_deal_value,
                          recent_activities=recent_activities)


# ========== COMPANIES ROUTES ==========

@crm_bp.route('/companies')
@login_required
def companies():
    """List all companies"""
    # Get search and filter params
    search = request.args.get('search', '')
    status = request.args.get('status', '')

    # Build query
    query = Company.query.filter_by(tenant_id=g.current_tenant.id)

    if search:
        query = query.filter(Company.name.ilike(f'%{search}%'))
    if status:
        query = query.filter_by(status=status)

    companies = query.order_by(Company.name.asc()).all()

    return render_template('crm/companies/index.html',
                          title='Companies',
                          companies=companies,
                          search=search,
                          status=status)


@crm_bp.route('/companies/<int:company_id>')
@login_required
def company_detail(company_id):
    """View company details"""
    company = Company.query.get_or_404(company_id)

    # Verify tenant access
    if company.tenant_id != g.current_tenant.id:
        return "Access denied", 403

    # Get related data
    contacts = company.contacts.all()
    deals = company.deals.all()
    activities = company.activities.order_by(Activity.created_at.desc()).limit(20).all()

    return render_template('crm/companies/detail.html',
                          title=company.name,
                          company=company,
                          contacts=contacts,
                          deals=deals,
                          activities=activities)


@crm_bp.route('/companies/create', methods=['POST'])
@login_required
def create_company():
    """Create a new company"""
    data = request.get_json()

    name = data.get('name')
    if not name:
        return jsonify({'error': 'Company name is required'}), 400

    company = Company(
        tenant_id=g.current_tenant.id,
        name=name,
        website=data.get('website'),
        industry=data.get('industry'),
        company_size=data.get('company_size'),
        annual_revenue=data.get('annual_revenue'),
        address_street=data.get('address_street'),
        address_city=data.get('address_city'),
        address_state=data.get('address_state'),
        address_postal_code=data.get('address_postal_code'),
        address_country=data.get('address_country'),
        phone=data.get('phone'),
        linkedin_url=data.get('linkedin_url'),
        twitter_handle=data.get('twitter_handle'),
        description=data.get('description'),
        tags=data.get('tags'),
        status=data.get('status', 'active'),
        lifecycle_stage=data.get('lifecycle_stage', 'lead'),
        owner_id=current_user.id
    )

    db.session.add(company)
    db.session.commit()

    return jsonify(company.to_dict()), 201


@crm_bp.route('/companies/<int:company_id>/update', methods=['POST'])
@login_required
def update_company(company_id):
    """Update company details"""
    company = Company.query.get_or_404(company_id)

    # Verify tenant access
    if company.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    # Update fields
    if 'name' in data:
        company.name = data['name']
    if 'website' in data:
        company.website = data['website']
    if 'industry' in data:
        company.industry = data['industry']
    if 'company_size' in data:
        company.company_size = data['company_size']
    if 'annual_revenue' in data:
        company.annual_revenue = data['annual_revenue']
    if 'address_street' in data:
        company.address_street = data['address_street']
    if 'address_city' in data:
        company.address_city = data['address_city']
    if 'address_state' in data:
        company.address_state = data['address_state']
    if 'address_postal_code' in data:
        company.address_postal_code = data['address_postal_code']
    if 'address_country' in data:
        company.address_country = data['address_country']
    if 'phone' in data:
        company.phone = data['phone']
    if 'linkedin_url' in data:
        company.linkedin_url = data['linkedin_url']
    if 'twitter_handle' in data:
        company.twitter_handle = data['twitter_handle']
    if 'description' in data:
        company.description = data['description']
    if 'tags' in data:
        company.tags = data['tags']
    if 'status' in data:
        company.status = data['status']
    if 'lifecycle_stage' in data:
        company.lifecycle_stage = data['lifecycle_stage']

    company.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(company.to_dict())


@crm_bp.route('/companies/<int:company_id>', methods=['DELETE'])
@login_required
def delete_company(company_id):
    """Delete a company"""
    company = Company.query.get_or_404(company_id)

    # Verify tenant access
    if company.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(company)
    db.session.commit()

    return jsonify({'success': True})


@crm_bp.route('/companies/import', methods=['POST'])
@login_required
def import_companies():
    """Bulk import companies from CSV file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400

    try:
        results = CSVImportService.import_companies(
            file,
            tenant_id=g.current_tenant.id,
            owner_id=current_user.id
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@crm_bp.route('/companies/import/template')
@login_required
def download_company_template():
    """Download CSV template for company import"""
    csv_content = CSVImportService.generate_company_template()

    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=company_import_template.csv'

    return response


# ========== CONTACTS ROUTES ==========

@crm_bp.route('/contacts')
@login_required
def contacts():
    """List all contacts"""
    # Get search and filter params
    search = request.args.get('search', '')
    lifecycle_stage = request.args.get('lifecycle_stage', '')
    company_id = request.args.get('company_id', '')

    # Build query
    query = Contact.query.filter_by(tenant_id=g.current_tenant.id)

    if search:
        query = query.filter(
            db.or_(
                Contact.first_name.ilike(f'%{search}%'),
                Contact.last_name.ilike(f'%{search}%'),
                Contact.email.ilike(f'%{search}%')
            )
        )
    if lifecycle_stage:
        query = query.filter_by(lifecycle_stage=lifecycle_stage)
    if company_id:
        query = query.filter_by(company_id=int(company_id))

    contacts = query.order_by(Contact.last_name.asc(), Contact.first_name.asc()).all()

    # Get companies for filter dropdown
    companies = Company.query.filter_by(tenant_id=g.current_tenant.id).order_by(Company.name.asc()).all()

    return render_template('crm/contacts/index.html',
                          title='Contacts',
                          contacts=contacts,
                          companies=companies,
                          search=search,
                          lifecycle_stage=lifecycle_stage,
                          company_id=company_id)


@crm_bp.route('/contacts/<int:contact_id>')
@login_required
def contact_detail(contact_id):
    """View contact details"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify tenant access
    if contact.tenant_id != g.current_tenant.id:
        return "Access denied", 403

    # Get related data
    activities = contact.activities.order_by(Activity.created_at.desc()).limit(20).all()
    deals = contact.deals.all()

    return render_template('crm/contacts/detail.html',
                          title=f'{contact.first_name} {contact.last_name}',
                          contact=contact,
                          activities=activities,
                          deals=deals)


@crm_bp.route('/contacts/create', methods=['POST'])
@login_required
def create_contact():
    """Create a new contact"""
    data = request.get_json()

    first_name = data.get('first_name')
    last_name = data.get('last_name')

    if not first_name or not last_name:
        return jsonify({'error': 'First name and last name are required'}), 400

    contact = Contact(
        tenant_id=g.current_tenant.id,
        first_name=first_name,
        last_name=last_name,
        email=data.get('email'),
        phone=data.get('phone'),
        mobile=data.get('mobile'),
        job_title=data.get('job_title'),
        company_id=data.get('company_id'),
        linkedin_url=data.get('linkedin_url'),
        twitter_handle=data.get('twitter_handle'),
        description=data.get('description'),
        tags=data.get('tags'),
        lifecycle_stage=data.get('lifecycle_stage', 'subscriber'),
        lead_score=data.get('lead_score', 0),
        owner_id=current_user.id
    )

    db.session.add(contact)
    db.session.commit()

    return jsonify(contact.to_dict()), 201


@crm_bp.route('/contacts/<int:contact_id>/update', methods=['POST'])
@login_required
def update_contact(contact_id):
    """Update contact details"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify tenant access
    if contact.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()

    # Update fields
    if 'first_name' in data:
        contact.first_name = data['first_name']
    if 'last_name' in data:
        contact.last_name = data['last_name']
    if 'email' in data:
        contact.email = data['email']
    if 'phone' in data:
        contact.phone = data['phone']
    if 'mobile' in data:
        contact.mobile = data['mobile']
    if 'job_title' in data:
        contact.job_title = data['job_title']
    if 'company_id' in data:
        contact.company_id = data['company_id']
    if 'linkedin_url' in data:
        contact.linkedin_url = data['linkedin_url']
    if 'twitter_handle' in data:
        contact.twitter_handle = data['twitter_handle']
    if 'description' in data:
        contact.description = data['description']
    if 'tags' in data:
        contact.tags = data['tags']
    if 'lifecycle_stage' in data:
        contact.lifecycle_stage = data['lifecycle_stage']
    if 'lead_score' in data:
        contact.lead_score = data['lead_score']

    contact.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(contact.to_dict())


@crm_bp.route('/contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    """Delete a contact"""
    contact = Contact.query.get_or_404(contact_id)

    # Verify tenant access
    if contact.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(contact)
    db.session.commit()

    return jsonify({'success': True})


@crm_bp.route('/contacts/import', methods=['POST'])
@login_required
def import_contacts():
    """Bulk import contacts from CSV file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400

    try:
        results = CSVImportService.import_contacts(
            file,
            tenant_id=g.current_tenant.id,
            owner_id=current_user.id
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@crm_bp.route('/contacts/import/template')
@login_required
def download_contact_template():
    """Download CSV template for contact import"""
    csv_content = CSVImportService.generate_contact_template()

    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=contact_import_template.csv'

    return response


# ========== PIPELINE ROUTES ==========

@crm_bp.route('/pipelines/create-default', methods=['POST'])
@login_required
def create_default_pipeline_route():
    """Create the default deal pipeline"""
    try:
        pipeline = create_default_deal_pipeline(g.current_tenant.id)
        return jsonify({'success': True, 'pipeline_id': pipeline.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== DEALS ROUTES ==========

@crm_bp.route('/deals')
@login_required
def deals():
    """Deals pipeline kanban view"""
    # Get default pipeline or first pipeline
    pipeline = DealPipeline.query.filter_by(
        tenant_id=g.current_tenant.id,
        is_default=True
    ).first()

    if not pipeline:
        pipeline = DealPipeline.query.filter_by(tenant_id=g.current_tenant.id).first()

    if not pipeline:
        # No pipeline exists, redirect to dashboard with message
        return render_template('crm/deals/no_pipeline.html', title='Deals Pipeline')

    # Get all stages for this pipeline
    stages = pipeline.stages

    # Get all deals in this pipeline organized by stage
    deals_by_stage = {}
    for stage in stages:
        deals = Deal.query.filter_by(
            tenant_id=g.current_tenant.id,
            pipeline_id=pipeline.id,
            stage_id=stage.id
        ).order_by(Deal.position.asc()).all()
        deals_by_stage[stage.id] = deals

    return render_template('crm/deals/index.html',
                          title='Deals Pipeline',
                          pipeline=pipeline,
                          stages=stages,
                          deals_by_stage=deals_by_stage)


@crm_bp.route('/deals/<int:deal_id>')
@login_required
def deal_detail(deal_id):
    """View deal details"""
    deal = Deal.query.get_or_404(deal_id)

    # Verify tenant access
    if deal.tenant_id != g.current_tenant.id:
        return "Access denied", 403

    # Get related data
    activities = deal.activities.order_by(Activity.created_at.desc()).limit(20).all()

    return render_template('crm/deals/detail.html',
                          title=deal.name,
                          deal=deal,
                          activities=activities)


@crm_bp.route('/deals/create', methods=['POST'])
@login_required
def create_deal():
    """Create a new deal"""
    data = request.get_json()

    name = data.get('name')
    if not name:
        return jsonify({'error': 'Deal name is required'}), 400

    # Get default pipeline
    pipeline = DealPipeline.query.filter_by(
        tenant_id=g.current_tenant.id,
        is_default=True
    ).first()

    if not pipeline:
        pipeline = DealPipeline.query.filter_by(tenant_id=g.current_tenant.id).first()

    if not pipeline:
        return jsonify({'error': 'No deal pipeline found'}), 400

    # Get first stage of pipeline
    first_stage = pipeline.stages[0] if pipeline.stages else None
    if not first_stage:
        return jsonify({'error': 'No stages in pipeline'}), 400

    deal = Deal(
        tenant_id=g.current_tenant.id,
        name=name,
        amount=data.get('amount'),
        pipeline_id=pipeline.id,
        stage_id=first_stage.id,
        probability=first_stage.probability,
        company_id=data.get('company_id'),
        description=data.get('description'),
        close_date=datetime.strptime(data['close_date'], '%Y-%m-%d') if data.get('close_date') else None,
        owner_id=current_user.id
    )

    db.session.add(deal)
    db.session.commit()

    return jsonify(deal.to_dict()), 201


@crm_bp.route('/deals/<int:deal_id>/move', methods=['POST'])
@login_required
def move_deal(deal_id):
    """Move deal to a different stage"""
    deal = Deal.query.get_or_404(deal_id)

    # Verify tenant access
    if deal.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    new_stage_id = data.get('stage_id')
    new_position = data.get('position', 0)

    if not new_stage_id:
        return jsonify({'error': 'Stage ID is required'}), 400

    # Verify stage belongs to same pipeline
    new_stage = DealStage.query.get_or_404(new_stage_id)
    if new_stage.pipeline_id != deal.pipeline_id:
        return jsonify({'error': 'Invalid stage'}), 400

    # Update deal
    deal.stage_id = new_stage_id
    deal.probability = new_stage.probability
    deal.position = new_position

    # Check if stage is closed won/lost
    if new_stage.is_closed_won:
        deal.status = 'won'
    elif new_stage.is_closed_lost:
        deal.status = 'lost'
    else:
        deal.status = 'open'

    db.session.commit()

    return jsonify(deal.to_dict())


@crm_bp.route('/deals/<int:deal_id>', methods=['DELETE'])
@login_required
def delete_deal(deal_id):
    """Delete a deal"""
    deal = Deal.query.get_or_404(deal_id)

    # Verify tenant access
    if deal.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(deal)
    db.session.commit()

    return jsonify({'success': True})


# ========== LEADS ROUTES ==========

@crm_bp.route('/leads')
@login_required
def leads():
    """List all leads"""
    leads = Lead.query.filter_by(
        tenant_id=g.current_tenant.id,
        converted=False
    ).order_by(Lead.created_at.desc()).all()

    return render_template('crm/leads/index.html',
                          title='Leads',
                          leads=leads)


@crm_bp.route('/leads/create', methods=['POST'])
@login_required
def create_lead():
    """Create a new lead"""
    data = request.get_json()

    lead = Lead(
        tenant_id=g.current_tenant.id,
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data.get('email'),
        phone=data.get('phone'),
        company_name=data.get('company_name'),
        job_title=data.get('job_title'),
        source=data.get('source'),
        status=data.get('status', 'new'),
        lead_score=data.get('lead_score', 0),
        owner_id=current_user.id
    )

    db.session.add(lead)
    db.session.commit()

    return jsonify(lead.to_dict()), 201


@crm_bp.route('/leads/<int:lead_id>', methods=['DELETE'])
@login_required
def delete_lead(lead_id):
    """Delete a lead"""
    lead = Lead.query.get_or_404(lead_id)

    # Verify tenant access
    if lead.tenant_id != g.current_tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(lead)
    db.session.commit()

    return jsonify({'success': True})


# ========== ACTIVITIES ROUTES ==========

@crm_bp.route('/activities')
@login_required
def activities():
    """List all activities"""
    activities = Activity.query.filter_by(
        tenant_id=g.current_tenant.id
    ).order_by(Activity.created_at.desc()).limit(100).all()

    return render_template('crm/activities/index.html',
                          title='Activities',
                          activities=activities)


@crm_bp.route('/activities/create', methods=['POST'])
@login_required
def create_activity():
    """Log a new activity"""
    data = request.get_json()

    activity = Activity(
        tenant_id=g.current_tenant.id,
        activity_type=data.get('activity_type', 'note'),
        subject=data.get('subject'),
        description=data.get('description'),
        company_id=data.get('company_id'),
        contact_id=data.get('contact_id'),
        deal_id=data.get('deal_id'),
        scheduled_at=datetime.strptime(data['scheduled_at'], '%Y-%m-%dT%H:%M') if data.get('scheduled_at') else None,
        completed=data.get('completed', False),
        created_by_id=current_user.id
    )

    db.session.add(activity)
    db.session.commit()

    return jsonify(activity.to_dict()), 201
