from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from urllib.parse import urlparse
from app import db, limiter
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm, RegistrationForm
from app.models.user import User


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
        user = User.query.filter_by(email=form.email.data.lower()).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))

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
            plan='free'  # Default to free plan
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Auto-login the user
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

                flash(f'Welcome to Soloquy, {user.full_name}! You\'ve been added to {invitation.tenant.name}.', 'success')
                return redirect(url_for('tenant.home'))

        # No invitation - redirect to workspace creation wizard
        flash(f'Welcome to Soloquy, {user.full_name}! Let\'s create your workspace.', 'success')
        return redirect(url_for('tenant.wizard'))

    return render_template('auth/register.html', form=form, title='Register')


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
