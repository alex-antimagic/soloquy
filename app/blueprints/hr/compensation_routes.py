"""
Compensation Planning Routes
Handles compensation management endpoints
"""
from flask import render_template, request, jsonify, g, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from app.blueprints.hr import hr_bp
from app.models.employee import Employee
from app.models.compensation_change import CompensationChange
from app import db
from datetime import datetime, date, timedelta
from sqlalchemy import desc, or_


def hr_admin_required(f):
    """Decorator to require HR admin access (owner/admin role)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.current_tenant:
            flash('Please select a workspace first.', 'warning')
            return redirect(url_for('tenant.home'))

        role = current_user.get_role_in_tenant(g.current_tenant.id)
        if role not in ['owner', 'admin']:
            flash('Access denied. Only workspace admins can access compensation data.', 'danger')
            return redirect(url_for('hr.index'))

        return f(*args, **kwargs)
    return decorated_function


@hr_bp.route('/compensation')
@login_required
@hr_admin_required
def compensation():
    """Compensation planning dashboard"""
    tenant = g.current_tenant

    # Get upcoming compensation changes (planned/approved, not yet implemented)
    upcoming_changes = CompensationChange.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        CompensationChange.effective_date >= date.today(),
        CompensationChange.status.in_(['planned', 'approved'])
    ).order_by(CompensationChange.effective_date.asc()).all()

    # Get recent compensation history (last 90 days)
    ninety_days_ago = date.today() - timedelta(days=90)
    recent_changes = CompensationChange.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        CompensationChange.effective_date >= ninety_days_ago,
        CompensationChange.status == 'implemented'
    ).order_by(CompensationChange.effective_date.desc()).all()

    # Calculate metrics
    total_planned_increase = sum(
        float(change.raise_amount or 0) for change in upcoming_changes
        if change.change_type in ['salary_change', 'raise', 'promotion']
    )

    total_planned_bonuses = sum(
        float(change.bonus_amount or 0) for change in upcoming_changes
        if change.change_type == 'bonus'
    )

    pending_approvals = CompensationChange.query.join(Employee).filter(
        Employee.tenant_id == tenant.id,
        CompensationChange.status == 'planned'
    ).count()

    return render_template('hr/compensation/index.html',
                          title='Compensation Planning',
                          upcoming_changes=upcoming_changes,
                          recent_changes=recent_changes,
                          total_planned_increase=total_planned_increase,
                          total_planned_bonuses=total_planned_bonuses,
                          pending_approvals=pending_approvals)


@hr_bp.route('/compensation/plan-change', methods=['GET', 'POST'])
@login_required
@hr_admin_required
def plan_change():
    """Plan a new compensation change"""
    tenant = g.current_tenant

    if request.method == 'POST':
        data = request.form

        # Get employee
        employee_id = data.get('employee_id')
        employee = Employee.query.filter_by(
            id=employee_id,
            tenant_id=tenant.id
        ).first()

        if not employee:
            flash('Employee not found.', 'danger')
            return redirect(url_for('hr.compensation'))

        # Create compensation change
        change = CompensationChange(
            tenant_id=tenant.id,
            employee_id=employee.id,
            change_type=data.get('change_type'),
            effective_date=datetime.strptime(data.get('effective_date'), '%Y-%m-%d').date(),
            reason=data.get('reason'),
            notes=data.get('notes'),
            created_by_user_id=current_user.id,
            status='planned'
        )

        # Set type-specific fields
        change_type = data.get('change_type')

        if change_type in ['salary_change', 'raise', 'promotion']:
            change.previous_salary = employee.salary
            change.previous_salary_currency = employee.salary_currency

            new_salary = data.get('new_salary')
            if new_salary:
                change.new_salary = float(new_salary)
                change.new_salary_currency = data.get('new_salary_currency', 'USD')

                # Calculate raise amount and percentage
                if employee.salary:
                    change.raise_amount = change.new_salary - float(employee.salary)
                    change.raise_percentage = (change.raise_amount / float(employee.salary)) * 100

        elif change_type == 'bonus':
            bonus_amount = data.get('bonus_amount')
            if bonus_amount:
                change.bonus_amount = float(bonus_amount)
                change.bonus_currency = data.get('bonus_currency', 'USD')
                change.bonus_type = data.get('bonus_type')

        db.session.add(change)
        db.session.commit()

        flash(f'Compensation change planned for {employee.full_name}.', 'success')
        return redirect(url_for('hr.compensation'))

    # GET request - show form
    employees = Employee.query.filter_by(
        tenant_id=tenant.id,
        status='active'
    ).order_by(Employee.last_name.asc()).all()

    return render_template('hr/compensation/plan_change.html',
                          title='Plan Compensation Change',
                          employees=employees)


@hr_bp.route('/compensation/<int:change_id>')
@login_required
@hr_admin_required
def compensation_change_detail(change_id):
    """Get compensation change details (AJAX endpoint)"""
    tenant = g.current_tenant

    change = CompensationChange.query.join(Employee).filter(
        CompensationChange.id == change_id,
        Employee.tenant_id == tenant.id
    ).first_or_404()

    return jsonify({
        'id': change.id,
        'employee_id': change.employee_id,
        'employee_name': change.employee.full_name,
        'change_type': change.change_type,
        'effective_date': change.effective_date.isoformat(),
        'previous_salary': float(change.previous_salary) if change.previous_salary else None,
        'new_salary': float(change.new_salary) if change.new_salary else None,
        'raise_amount': float(change.raise_amount) if change.raise_amount else None,
        'raise_percentage': change.raise_percentage,
        'bonus_amount': float(change.bonus_amount) if change.bonus_amount else None,
        'bonus_type': change.bonus_type,
        'reason': change.reason,
        'notes': change.notes,
        'status': change.status,
        'created_at': change.created_at.isoformat(),
        'created_by': change.created_by.full_name if change.created_by else None,
        'approved_by': change.approved_by.full_name if change.approved_by else None,
        'approved_at': change.approved_at.isoformat() if change.approved_at else None
    })


@hr_bp.route('/compensation/<int:change_id>/approve', methods=['POST'])
@login_required
@hr_admin_required
def approve_compensation_change(change_id):
    """Approve a planned compensation change"""
    tenant = g.current_tenant

    change = CompensationChange.query.join(Employee).filter(
        CompensationChange.id == change_id,
        Employee.tenant_id == tenant.id
    ).first_or_404()

    if change.status != 'planned':
        return jsonify({'error': f'Change is already {change.status}'}), 400

    change.approve(current_user)
    db.session.commit()

    flash(f'Compensation change approved for {change.employee.full_name}.', 'success')
    return jsonify({
        'success': True,
        'message': 'Compensation change approved',
        'status': change.status
    })


@hr_bp.route('/compensation/<int:change_id>/implement', methods=['POST'])
@login_required
@hr_admin_required
def implement_compensation_change(change_id):
    """Mark a compensation change as implemented"""
    tenant = g.current_tenant

    change = CompensationChange.query.join(Employee).filter(
        CompensationChange.id == change_id,
        Employee.tenant_id == tenant.id
    ).first_or_404()

    if change.status not in ['planned', 'approved']:
        return jsonify({'error': f'Change is already {change.status}'}), 400

    change.implement()
    db.session.commit()

    flash(f'Compensation change implemented for {change.employee.full_name}.', 'success')
    return jsonify({
        'success': True,
        'message': 'Compensation change implemented',
        'status': change.status,
        'employee_salary': float(change.employee.salary) if change.employee.salary else None
    })


@hr_bp.route('/compensation/<int:change_id>/cancel', methods=['POST'])
@login_required
@hr_admin_required
def cancel_compensation_change(change_id):
    """Cancel a planned compensation change"""
    tenant = g.current_tenant

    change = CompensationChange.query.join(Employee).filter(
        CompensationChange.id == change_id,
        Employee.tenant_id == tenant.id
    ).first_or_404()

    if change.status not in ['planned', 'approved']:
        return jsonify({'error': f'Cannot cancel a change that is {change.status}'}), 400

    change.cancel()
    db.session.commit()

    flash(f'Compensation change cancelled for {change.employee.full_name}.', 'success')
    return jsonify({
        'success': True,
        'message': 'Compensation change cancelled',
        'status': change.status
    })


@hr_bp.route('/compensation/employee/<int:employee_id>')
@login_required
@hr_admin_required
def employee_compensation_history(employee_id):
    """Get compensation history for a specific employee (AJAX endpoint)"""
    tenant = g.current_tenant

    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant.id
    ).first_or_404()

    # Get all compensation changes for this employee
    changes = CompensationChange.query.filter_by(
        employee_id=employee.id
    ).order_by(CompensationChange.effective_date.desc()).all()

    return jsonify({
        'employee_id': employee.id,
        'employee_name': employee.full_name,
        'current_salary': float(employee.salary) if employee.salary else None,
        'current_salary_currency': employee.salary_currency,
        'changes': [
            {
                'id': change.id,
                'change_type': change.change_type,
                'effective_date': change.effective_date.isoformat(),
                'previous_salary': float(change.previous_salary) if change.previous_salary else None,
                'new_salary': float(change.new_salary) if change.new_salary else None,
                'raise_amount': float(change.raise_amount) if change.raise_amount else None,
                'raise_percentage': change.raise_percentage,
                'bonus_amount': float(change.bonus_amount) if change.bonus_amount else None,
                'bonus_type': change.bonus_type,
                'reason': change.reason,
                'status': change.status,
                'created_at': change.created_at.isoformat()
            }
            for change in changes
        ]
    })
