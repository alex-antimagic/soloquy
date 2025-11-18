"""
Security decorators for access control
"""
from functools import wraps
from flask import g, abort
from flask_login import current_user


def require_tenant_access(f):
    """
    Decorator to ensure user has access to the current tenant
    Must be used after @login_required
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if current tenant is set
        if not g.current_tenant:
            abort(403, description="No tenant selected")

        # Verify user has access to current tenant
        if not current_user.has_tenant_access(g.current_tenant.id):
            abort(403, description="You do not have access to this workspace")

        return f(*args, **kwargs)

    return decorated_function


def require_tenant_role(*allowed_roles):
    """
    Decorator to ensure user has specific role in current tenant
    Usage: @require_tenant_role('owner', 'admin')
    Must be used after @login_required and @require_tenant_access
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.current_tenant:
                abort(403, description="No tenant selected")

            user_role = current_user.get_role_in_tenant(g.current_tenant.id)

            if user_role not in allowed_roles:
                abort(403, description=f"This action requires {' or '.join(allowed_roles)} role")

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_superadmin(f):
    """
    Decorator to ensure user is a superadmin
    Provides global admin access across all tenants
    Must be used after @login_required
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401, description="Authentication required")

        if not current_user.is_superadmin:
            abort(403, description="Superadmin access required")

        return f(*args, **kwargs)

    return decorated_function
