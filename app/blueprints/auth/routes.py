from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user
from urllib.parse import urlparse
from datetime import datetime
from app import db, limiter
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.email_service import email_service


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('tenant.home'))

    form = LoginForm()

    # Check for CSRF errors and show user-friendly message
    if request.method == 'POST' and not form.validate_on_submit():
        if 'csrf_token' in form.errors:
            flash('Your session expired. Please refresh the page and try again.', 'warning')
            return redirect(url_for('auth.login'))

    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()

        # Get request context for audit logging
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')

        # Check if account is locked
        if user and user.is_account_locked():
            error_message = 'Account temporarily locked due to multiple failed login attempts'
            AuditLog.log_login_attempt(email, success=False, ip_address=ip_address,
                                     user_agent=user_agent, error_message=error_message)
            flash('Your account has been temporarily locked due to multiple failed login attempts. Please try again later or reset your password.', 'danger')
            return redirect(url_for('auth.login'))

        if user and user.check_password(form.password.data):
            if not user.is_active:
                error_message = 'Account deactivated'
                AuditLog.log_login_attempt(email, success=False, ip_address=ip_address,
                                         user_agent=user_agent, error_message=error_message)
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))

            # Log successful login
            AuditLog.log_login_attempt(email, success=True, ip_address=ip_address, user_agent=user_agent)

            # Regenerate session to prevent session fixation
            session.permanent = True
            session.modified = True

            login_user(user, remember=form.remember_me.data)
            user.is_online = True
            db.session.commit()

            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('tenant.home')

            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page)
        else:
            # Failed login attempt
            error_message = 'Invalid credentials'
            AuditLog.log_login_attempt(email, success=False, ip_address=ip_address,
                                     user_agent=user_agent, error_message=error_message)

            # Check if account should be locked after this failed attempt
            if user and AuditLog.should_lock_account(user.id):
                user.lock_account()

                # Send security alert to admin
                details = {
                    'ip_address': ip_address,
                    'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'attempt_count': AuditLog.get_failed_login_attempts(user.id)
                }
                email_service.send_security_alert_email(user, 'account_lockout', details)

                flash('Too many failed login attempts. Your account has been temporarily locked for security. Please check your email or reset your password.', 'danger')
            else:
                flash('Invalid email or password. Please try again.', 'danger')

    return render_template('auth/login.html', form=form, title='Sign In')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    """Registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('tenant.home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        from app.models.invitation import Invitation
        from app.models.tenant import TenantMembership

        user = User(
            email=form.email.data.lower(),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            plan='free',  # Default to free plan
            email_confirmed=False  # Require email confirmation
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Generate confirmation token and send confirmation email
        token = user.generate_confirmation_token()
        confirmation_url = url_for('auth.confirm_email', token=token, _external=True)
        email_service.send_email_confirmation(user, confirmation_url)

        # Auto-login the user (but they'll need to confirm email)
        session.permanent = True
        session.modified = True
        login_user(user, remember=True)
        user.is_online = True
        db.session.commit()

        # Check if user has a pending invitation token
        invitation_token = session.pop('invitation_token', None)

        if invitation_token:
            # User registered via invitation link
            invitation = Invitation.query.filter_by(token=invitation_token).first()

            if invitation and invitation.is_pending() and invitation.email.lower() == user.email:
                # Add user to workspace
                membership = TenantMembership(
                    tenant_id=invitation.tenant_id,
                    user_id=user.id,
                    role=invitation.role
                )
                db.session.add(membership)

                invitation.mark_as_accepted()
                db.session.commit()

                # Set current tenant
                session['current_tenant_id'] = invitation.tenant_id

                flash(f'Welcome to Soloquy, {user.full_name}! Please check your email to confirm your account.', 'success')
                return redirect(url_for('tenant.home'))

        # No invitation - redirect to workspace creation wizard
        flash(f'Welcome to Soloquy, {user.full_name}! Please check your email to confirm your account.', 'success')
        return redirect(url_for('tenant.wizard'))

    return render_template('auth/register.html', form=form, title='Register')


@auth_bp.route('/confirm-email/<token>')
def confirm_email(token):
    """Confirm email address with token"""
    if current_user.is_authenticated and current_user.email_confirmed:
        flash('Your email is already confirmed.', 'info')
        return redirect(url_for('tenant.home'))

    # Find user by token
    user = User.find_by_confirmation_token(token)

    if not user:
        flash('Invalid or expired confirmation link.', 'danger')
        return redirect(url_for('auth.login'))

    # Confirm email
    if user.confirm_email(token):
        flash('Your email has been confirmed! You can now access all features.', 'success')
        if current_user.is_authenticated:
            return redirect(url_for('tenant.home'))
        else:
            return redirect(url_for('auth.login'))
    else:
        flash('Invalid or expired confirmation link.', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('tenant.home'))

    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()

        # Always show success message to prevent email enumeration
        flash('If an account exists with that email, you will receive password reset instructions.', 'info')

        if user:
            # Generate reset token
            token = user.generate_password_reset_token()

            # Send password reset email
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            email_service.send_password_reset_email(user, reset_url)

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form, title='Forgot Password')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('tenant.home'))

    # Find user by token
    user = User.find_by_reset_token(token)

    if not user:
        flash('Invalid or expired password reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        # Reset password
        if user.reset_password(token, form.password.data):
            flash('Your password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid or expired password reset link. Please request a new one.', 'danger')
            return redirect(url_for('auth.forgot_password'))

    return render_template('auth/reset_password.html', form=form, title='Reset Password', token=token)


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Logout user"""
    if current_user.is_authenticated:
        current_user.is_online = False
        db.session.commit()

    # Create response FIRST
    response = redirect(url_for('auth.login'))

    # Explicitly delete all auth-related cookies
    # This prevents re-authentication from remember_me cookie
    response.set_cookie('session', '', expires=0, path='/', samesite='Lax', httponly=True)
    response.set_cookie('remember_token', '', expires=0, path='/', samesite='Lax', httponly=True)

    # Logout user and clear session
    logout_user()
    session.clear()

    return response
