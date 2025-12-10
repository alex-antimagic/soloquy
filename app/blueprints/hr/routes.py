"""
HR Routes
Handles HR/People management endpoints
"""
from flask import render_template, request, jsonify, g, redirect, url_for, flash
from flask_login import login_required, current_user
from app.blueprints.hr import hr_bp
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.employee import Employee
from app.models.onboarding_plan import OnboardingPlan, OnboardingTask
from app.models.pto_request import PTORequest
from app.models.job_posting import JobPosting
from app.services.hr_service import hr_service
from app.services.email_service import email_service
from app.services.applet_manager import is_applet_enabled
from app import db
from datetime import datetime, date, timedelta
from sqlalchemy import func


@hr_bp.before_request
@login_required
def check_access():
    """Ensure user has access to HR applet"""
    if not g.current_tenant:
        flash('Please select a workspace first.', 'warning')
        return redirect(url_for('tenant.home'))

    # Check if HR applet is enabled
    if not is_applet_enabled(g.current_tenant.id, 'hr'):
        flash('HR/People is not enabled for this workspace.', 'warning')
        return redirect(url_for('tenant.home'))


@hr_bp.route('/')
@login_required
def index():
    """HR Dashboard"""
    tenant = g.current_tenant

    # Get aggregate metrics
    total_employees = Employee.query.filter_by(
        tenant_id=tenant.id,
        status='active'
    ).count()

    open_positions = JobPosting.query.filter_by(
        tenant_id=tenant.id,
        status='published'
    ).count()

    pending_pto = PTORequest.query.filter_by(
        tenant_id=tenant.id,
        status='pending'
    ).count()

    # New hires this month
    first_day_of_month = date.today().replace(day=1)
    new_hires_count = Employee.query.filter(
        Employee.tenant_id == tenant.id,
        Employee.hire_date >= first_day_of_month,
        Employee.status == 'active'
    ).count()

    # Active onboarding plans (started in last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    active_onboarding = OnboardingPlan.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        OnboardingPlan.start_date >= thirty_days_ago
    ).order_by(OnboardingPlan.start_date.desc()).limit(5).all()

    # Upcoming interviews (next 7 days)
    today = datetime.utcnow()
    next_week = today + timedelta(days=7)
    upcoming_interviews = Interview.query.join(Candidate).filter(
        Candidate.tenant_id == tenant.id,
        Interview.scheduled_date >= today,
        Interview.scheduled_date <= next_week,
        Interview.status == 'scheduled'
    ).order_by(Interview.scheduled_date.asc()).limit(10).all()

    # Upcoming PTO (next 30 days)
    thirty_days_ahead = date.today() + timedelta(days=30)
    upcoming_pto = PTORequest.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        PTORequest.start_date <= thirty_days_ahead,
        PTORequest.end_date >= date.today(),
        PTORequest.status.in_(['approved', 'pending'])
    ).order_by(PTORequest.start_date.asc()).limit(10).all()

    return render_template('hr/index.html',
                          title='HR Dashboard',
                          total_employees=total_employees,
                          open_positions=open_positions,
                          pending_pto=pending_pto,
                          new_hires_count=new_hires_count,
                          active_onboarding=active_onboarding,
                          upcoming_interviews=upcoming_interviews,
                          upcoming_pto=upcoming_pto)


# ========== RECRUITMENT ROUTES ==========

@hr_bp.route('/recruitment')
@login_required
def recruitment():
    """Recruitment dashboard - candidate pipeline"""
    tenant = g.current_tenant

    # Get all candidates grouped by status
    candidates = Candidate.query.filter_by(
        tenant_id=tenant.id
    ).order_by(Candidate.overall_score.desc()).all()

    # Group candidates by status for Kanban board
    candidates_by_status = {
        'applied': [],
        'screening': [],
        'interviewing': [],
        'offer_extended': [],
        'hired': [],
        'rejected': []
    }

    for candidate in candidates:
        status = candidate.status
        if status in candidates_by_status:
            candidates_by_status[status].append(candidate)

    # Get job postings for filters
    job_postings = JobPosting.query.filter_by(
        tenant_id=tenant.id
    ).order_by(JobPosting.created_at.desc()).all()

    return render_template('hr/recruitment/index.html',
                          title='Recruitment Pipeline',
                          candidates_by_status=candidates_by_status,
                          job_postings=job_postings)


@hr_bp.route('/recruitment/candidates/<int:candidate_id>')
@login_required
def candidate_detail(candidate_id):
    """Get candidate details (AJAX endpoint)"""
    tenant = g.current_tenant

    candidate = Candidate.query.filter_by(
        id=candidate_id,
        tenant_id=tenant.id
    ).first_or_404()

    # Get interview history
    interviews = Interview.query.filter_by(
        candidate_id=candidate.id
    ).order_by(Interview.scheduled_date.desc()).all()

    return jsonify({
        'id': candidate.id,
        'full_name': candidate.full_name,
        'email': candidate.email,
        'phone': candidate.phone,
        'position': candidate.position,
        'status': candidate.status,
        'applied_date': candidate.applied_date.isoformat(),
        'overall_score': candidate.overall_score,
        'category_scores': candidate.get_category_scores(),
        'skills': candidate.get_skills_list(),
        'experience_years': candidate.experience_years,
        'resume_url': candidate.resume_url,
        'linkedin_url': candidate.linkedin_url,
        'cover_letter': candidate.cover_letter,
        'notes': candidate.get_notes(),
        'interviews': [
            {
                'id': i.id,
                'type': i.interview_type,
                'scheduled_date': i.scheduled_date.isoformat(),
                'duration_minutes': i.duration_minutes,
                'status': i.status,
                'interviewers': i.interviewers_list,
                'location': i.location,
                'score': i.score,
                'feedback': i.feedback
            }
            for i in interviews
        ]
    })


@hr_bp.route('/recruitment/candidates/<int:candidate_id>/update-status', methods=['POST'])
@login_required
def update_candidate_status(candidate_id):
    """Update candidate status (for Kanban drag-and-drop)"""
    tenant = g.current_tenant

    candidate = Candidate.query.filter_by(
        id=candidate_id,
        tenant_id=tenant.id
    ).first_or_404()

    data = request.get_json()
    new_status = data.get('status')
    reason = data.get('reason')

    if new_status not in ['applied', 'screening', 'interviewing', 'offer_extended', 'hired', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400

    old_status = candidate.status
    candidate.update_status(new_status, reason)
    db.session.commit()

    # Send notification email if status changed to hired or rejected
    if new_status in ['hired', 'rejected', 'offer_extended']:
        email_service.send_candidate_status_update(
            candidate, old_status, new_status, reason
        )

    return jsonify({
        'success': True,
        'candidate_id': candidate.id,
        'old_status': old_status,
        'new_status': new_status
    })


@hr_bp.route('/recruitment/jobs')
@login_required
def job_postings_list():
    """List all job postings"""
    tenant = g.current_tenant

    # Get filter params
    status = request.args.get('status', '')

    query = JobPosting.query.filter_by(tenant_id=tenant.id)

    if status:
        query = query.filter_by(status=status)

    job_postings = query.order_by(JobPosting.created_at.desc()).all()

    return render_template('hr/recruitment/jobs/list.html',
                          title='Job Postings',
                          job_postings=job_postings,
                          status=status)


@hr_bp.route('/recruitment/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    """Job posting detail page"""
    tenant = g.current_tenant

    job = JobPosting.query.filter_by(
        id=job_id,
        tenant_id=tenant.id
    ).first_or_404()

    # Get candidates for this job
    candidates = Candidate.query.filter_by(
        job_posting_id=job.id
    ).order_by(Candidate.overall_score.desc()).all()

    return render_template('hr/recruitment/jobs/detail.html',
                          title=job.title,
                          job=job,
                          candidates=candidates)


@hr_bp.route('/recruitment/interviews')
@login_required
def interviews_list():
    """List all interviews"""
    tenant = g.current_tenant

    # Get upcoming interviews
    today = datetime.utcnow()
    interviews = Interview.query.join(Candidate).filter(
        Candidate.tenant_id == tenant.id,
        Interview.scheduled_date >= today
    ).order_by(Interview.scheduled_date.asc()).all()

    # Get past interviews
    past_interviews = Interview.query.join(Candidate).filter(
        Candidate.tenant_id == tenant.id,
        Interview.scheduled_date < today
    ).order_by(Interview.scheduled_date.desc()).limit(20).all()

    return render_template('hr/recruitment/interviews/list.html',
                          title='Interviews',
                          interviews=interviews,
                          past_interviews=past_interviews)


# ========== ONBOARDING ROUTES ==========

@hr_bp.route('/onboarding')
@login_required
def onboarding():
    """Onboarding dashboard"""
    tenant = g.current_tenant

    # Get active onboarding plans
    plans = OnboardingPlan.query.join(Employee).filter(
        Employee.tenant_id == tenant.id
    ).order_by(OnboardingPlan.start_date.desc()).all()

    return render_template('hr/onboarding/index.html',
                          title='Onboarding',
                          plans=plans)


@hr_bp.route('/onboarding/<int:plan_id>')
@login_required
def onboarding_detail(plan_id):
    """Onboarding plan detail"""
    plan = OnboardingPlan.query.filter_by(id=plan_id).first_or_404()

    # Verify tenant access
    if plan.employee.tenant_id != g.current_tenant.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('hr.onboarding'))

    # Get tasks grouped by category
    tasks = OnboardingTask.query.filter_by(
        plan_id=plan.id
    ).order_by(OnboardingTask.position).all()

    return render_template('hr/onboarding/detail.html',
                          title=f'Onboarding - {plan.employee.full_name}',
                          plan=plan,
                          tasks=tasks)


# ========== EMPLOYEE ROUTES ==========

@hr_bp.route('/employees')
@login_required
def employees():
    """Employee directory"""
    tenant = g.current_tenant

    # Get search and filter params
    search = request.args.get('search', '')
    department = request.args.get('department', '')
    status = request.args.get('status', '')

    # Build query
    query = Employee.query.filter_by(tenant_id=tenant.id)

    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Employee.first_name.ilike(search_term),
                Employee.last_name.ilike(search_term),
                Employee.email.ilike(search_term)
            )
        )

    if department:
        query = query.filter_by(department_name=department)

    if status:
        query = query.filter_by(status=status)

    employees = query.order_by(Employee.last_name.asc()).all()

    # Get unique departments for filter
    departments = db.session.query(Employee.department_name).filter(
        Employee.tenant_id == tenant.id,
        Employee.department_name.isnot(None)
    ).distinct().all()
    departments = [d[0] for d in departments]

    return render_template('hr/employees/directory.html',
                          title='Employees',
                          employees=employees,
                          departments=departments,
                          search=search,
                          selected_department=department,
                          selected_status=status)


@hr_bp.route('/employees/<int:employee_id>')
@login_required
def employee_profile(employee_id):
    """Employee profile page"""
    tenant = g.current_tenant

    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant.id
    ).first_or_404()

    # Get onboarding plan if exists
    onboarding_plan = employee.onboarding_plan

    # Get PTO requests
    pto_requests = PTORequest.query.filter_by(
        employee_id=employee.id
    ).order_by(PTORequest.start_date.desc()).all()

    return render_template('hr/employees/profile.html',
                          title=employee.full_name,
                          employee=employee,
                          onboarding_plan=onboarding_plan,
                          pto_requests=pto_requests)


# ========== TIME OFF ROUTES ==========

@hr_bp.route('/time-off')
@login_required
def time_off():
    """Time off dashboard"""
    tenant = g.current_tenant

    # Get pending requests
    pending_requests = PTORequest.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        PTORequest.status == 'pending'
    ).order_by(PTORequest.start_date.asc()).all()

    # Get upcoming approved time off
    upcoming_pto = PTORequest.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        PTORequest.start_date >= date.today(),
        PTORequest.status == 'approved'
    ).order_by(PTORequest.start_date.asc()).all()

    # Get team calendar data
    calendar_entries = hr_service.get_team_pto_calendar(
        tenant_id=tenant.id,
        days_ahead=30,
        include_pending=True
    )

    return render_template('hr/time_off/index.html',
                          title='Time Off',
                          pending_requests=pending_requests,
                          upcoming_pto=upcoming_pto,
                          calendar_entries=calendar_entries)


@hr_bp.route('/time-off/<int:request_id>/review', methods=['POST'])
@login_required
def review_pto_request(request_id):
    """Approve or deny PTO request"""
    tenant = g.current_tenant

    pto_request = PTORequest.query.filter_by(id=request_id).first_or_404()

    # Verify tenant access
    if pto_request.employee.tenant_id != tenant.id:
        return jsonify({'error': 'Access denied'}), 403

    if pto_request.status != 'pending':
        return jsonify({'error': f'Request is already {pto_request.status}'}), 400

    data = request.get_json()
    action = data.get('action')  # 'approve' or 'deny'
    denial_reason = data.get('denial_reason')

    reviewer_name = current_user.full_name

    if action == 'approve':
        pto_request.approve(reviewer_name)
        db.session.commit()

        email_service.send_pto_decision_notification(
            pto_request, 'approved', None
        )

        return jsonify({
            'success': True,
            'message': 'PTO request approved',
            'new_balance': pto_request.employee.pto_balance
        })

    elif action == 'deny':
        if not denial_reason:
            return jsonify({'error': 'Denial reason is required'}), 400

        pto_request.deny(reviewer_name, denial_reason)
        db.session.commit()

        email_service.send_pto_decision_notification(
            pto_request, 'denied', denial_reason
        )

        return jsonify({
            'success': True,
            'message': 'PTO request denied'
        })

    else:
        return jsonify({'error': 'Invalid action'}), 400
