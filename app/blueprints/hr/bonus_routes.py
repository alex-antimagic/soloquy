"""
Bonus Management Routes
Handles KPI-based bonus calculation and management
"""
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app, g
from flask_login import login_required, current_user
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from app.blueprints.hr import hr_bp
from app.models.monthly_financial_metrics import MonthlyFinancialMetrics
from app.models.bonus_rule import BonusRule
from app.models.bonus_calculation_log import BonusCalculationLog
from app.services.bonus_calculation_service import BonusCalculationService
from app.services.financial_metrics_service import FinancialMetricsService
from app import db


@hr_bp.route('/bonuses')
@login_required
def bonus_dashboard():
    """
    Bonus management dashboard showing overview and recent activity
    """
    from app.models.employee import Employee
    from app.models.compensation_change import CompensationChange

    current_tenant = g.current_tenant

    # Get employee record for current user
    employee = Employee.query.filter_by(
        tenant_id=current_tenant.id,
        user_id=current_user.id
    ).first()

    # Calculate monthly bonus target
    monthly_bonus_target = 0
    if employee and employee.salary and employee.bonus_target_percentage:
        monthly_bonus_target = float(employee.salary) * float(employee.bonus_target_percentage) / 100

    # Get employee's bonuses
    my_bonuses = []
    if employee:
        my_bonuses = CompensationChange.query.filter_by(
            tenant_id=current_tenant.id,
            employee_id=employee.id,
            change_type='bonus'
        ).order_by(CompensationChange.effective_date.desc()).limit(10).all()

    # Get recent months status
    recent_months = FinancialMetricsService.get_recent_months_status(current_tenant.id, months_back=6)

    # Get active bonus rules
    active_rules = BonusRule.query.filter_by(
        tenant_id=current_tenant.id,
        is_active=True
    ).all()

    # Get recent calculation logs
    recent_logs = BonusCalculationLog.query.filter_by(
        tenant_id=current_tenant.id
    ).order_by(BonusCalculationLog.calculation_date.desc()).limit(10).all()

    # Get YTD summary
    ytd_summary = FinancialMetricsService.get_metrics_summary(
        current_tenant.id,
        year=date.today().year
    )

    return render_template('hr/bonuses/dashboard.html',
                         recent_months=recent_months,
                         active_rules=active_rules,
                         recent_logs=recent_logs,
                         ytd_summary=ytd_summary,
                         current_tenant=current_tenant,
                         employee=employee,
                         my_bonuses=my_bonuses,
                         monthly_bonus_target=monthly_bonus_target)


@hr_bp.route('/bonuses/financial-metrics')
@login_required
def financial_metrics_list():
    """
    View/manage monthly financial metrics
    """
    current_tenant = g.current_tenant
    year = request.args.get('year', type=int, default=date.today().year)

    # Get all metrics for the year
    metrics = MonthlyFinancialMetrics.query.filter_by(
        tenant_id=current_tenant.id,
        year=year
    ).order_by(MonthlyFinancialMetrics.month.desc()).all()

    # Get available years
    years = db.session.query(MonthlyFinancialMetrics.year).filter_by(
        tenant_id=current_tenant.id
    ).distinct().order_by(MonthlyFinancialMetrics.year.desc()).all()
    available_years = [y[0] for y in years] if years else [year]

    return render_template('hr/bonuses/financial_metrics.html',
                         metrics=metrics,
                         year=year,
                         available_years=available_years,
                         current_tenant=current_tenant)


@hr_bp.route('/bonuses/financial-metrics/<int:year>/<int:month>', methods=['GET', 'POST'])
@login_required
def edit_financial_metrics(year, month):
    """
    Manual entry/edit form for financial metrics
    """
    current_tenant = g.current_tenant
    if request.method == 'POST':
        try:
            revenue = request.form.get('revenue', type=float)
            expenses = request.form.get('expenses', type=float)
            notes = request.form.get('notes', '')

            service = FinancialMetricsService()
            metrics = service.update_manual_metrics(
                tenant_id=current_tenant.id,
                year=year,
                month=month,
                revenue=revenue,
                expenses=expenses,
                user_id=current_user.id,
                notes=notes
            )

            flash(f'Financial metrics updated for {metrics.period_label}', 'success')
            return redirect(url_for('hr.financial_metrics_list'))

        except Exception as e:
            flash(f'Error updating metrics: {str(e)}', 'danger')

    # GET - show form
    metrics = FinancialMetricsService.get_metrics_for_period(current_tenant.id, year, month)
    period_label = date(year, month, 1).strftime('%B %Y')
    month_name = date(year, month, 1).strftime('%B')

    return render_template('hr/bonuses/edit_metrics.html',
                         metrics=metrics,
                         year=year,
                         month=month,
                         period_label=period_label,
                         month_name=month_name,
                         current_tenant=current_tenant)


@hr_bp.route('/bonuses/rules')
@login_required
def bonus_rules_list():
    """
    List all bonus rules with edit/delete actions
    """
    current_tenant = g.current_tenant
    rules = BonusRule.query.filter_by(
        tenant_id=current_tenant.id
    ).order_by(BonusRule.created_at.desc()).all()

    return render_template('hr/bonuses/rules.html',
                         rules=rules,
                         current_tenant=current_tenant)


@hr_bp.route('/bonuses/rules/create', methods=['GET', 'POST'])
@login_required
def create_bonus_rule():
    """
    Create new bonus rule
    """
    current_tenant = g.current_tenant
    if request.method == 'POST':
        try:
            import json

            rule_name = request.form.get('rule_name')
            metric = request.form.get('metric', 'net_revenue')
            operator = request.form.get('operator', '>=')
            threshold = request.form.get('threshold', type=float)
            bonus_type = request.form.get('bonus_type', 'performance')
            use_percentage = request.form.get('use_percentage') == 'on'
            description = request.form.get('description', '')

            # Create rule config
            rule_config = {
                'metric': metric,
                'operator': operator,
                'threshold': threshold
            }

            rule = BonusRule(
                tenant_id=current_tenant.id,
                rule_name=rule_name,
                rule_type='revenue_threshold',
                rule_config=json.dumps(rule_config),
                bonus_type=bonus_type,
                use_employee_target_percentage=use_percentage,
                applies_to_all_employees=True,
                is_active=True,
                created_by_user_id=current_user.id,
                description=description
            )

            db.session.add(rule)
            db.session.commit()

            flash(f'Bonus rule "{rule_name}" created successfully', 'success')
            return redirect(url_for('hr.bonus_rules_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating rule: {str(e)}', 'danger')
            return render_template('hr/bonuses/create_rule.html',
                                 current_tenant=current_tenant)

    return render_template('hr/bonuses/create_rule.html',
                         current_tenant=current_tenant)


@hr_bp.route('/bonuses/rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
def toggle_bonus_rule(rule_id):
    """
    Toggle bonus rule active/inactive
    """
    current_tenant = g.current_tenant
    try:
        rule = BonusRule.query.get_or_404(rule_id)

        if rule.tenant_id != current_tenant.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        rule.is_active = not rule.is_active
        db.session.commit()

        return jsonify({
            'success': True,
            'is_active': rule.is_active
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@hr_bp.route('/bonuses/calculate', methods=['POST'])
@login_required
def trigger_bonus_calculation():
    """
    Manually trigger bonus calculation for a specific period
    """
    current_tenant = g.current_tenant
    try:
        year = request.form.get('year', type=int)
        month = request.form.get('month', type=int)

        if not year or not month:
            flash('Year and month are required', 'danger')
            return redirect(url_for('hr.bonus_dashboard'))

        service = BonusCalculationService()
        result = service.calculate_monthly_bonuses(
            tenant_id=current_tenant.id,
            year=year,
            month=month,
            triggered_by='manual_admin',
            triggered_by_user_id=current_user.id
        )

        if result['success']:
            bonuses_created = result.get('bonuses_created', 0)
            total_amount = result.get('total_amount', 0)

            flash(
                f'Created {bonuses_created} bonuses totaling ${total_amount:,.2f}',
                'success'
            )

            # Redirect to compensation page to review bonuses
            return redirect(url_for('hr.compensation'))
        else:
            flash(f'Calculation failed: {result.get("error")}', 'danger')
            return redirect(url_for('hr.bonus_dashboard'))

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('hr.bonus_dashboard'))


@hr_bp.route('/bonuses/history')
@login_required
def bonus_calculation_history():
    """
    Audit log of all bonus calculations
    """
    current_tenant = g.current_tenant
    page = request.args.get('page', 1, type=int)
    per_page = 20

    logs = BonusCalculationLog.query.filter_by(
        tenant_id=current_tenant.id
    ).order_by(BonusCalculationLog.calculation_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('hr/bonuses/history.html',
                         logs=logs,
                         current_tenant=current_tenant)


@hr_bp.route('/bonuses/sync-quickbooks', methods=['POST'])
@login_required
def sync_quickbooks_metrics():
    """
    AJAX endpoint to sync QuickBooks P&L data for a specific month
    """
    current_tenant = g.current_tenant
    try:
        year = request.json.get('year', type=int)
        month = request.json.get('month', type=int)

        if not year or not month:
            return jsonify({'success': False, 'error': 'Year and month required'}), 400

        service = BonusCalculationService()
        success = service.sync_quickbooks_data(current_tenant.id, year, month)

        if success:
            # Get updated metrics
            metrics = FinancialMetricsService.get_metrics_for_period(
                current_tenant.id, year, month
            )

            return jsonify({
                'success': True,
                'revenue': float(metrics.total_revenue or 0),
                'expenses': float(metrics.total_expenses or 0),
                'net_revenue': float(metrics.net_revenue or 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to sync QuickBooks data. Check integration.'
            }), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
