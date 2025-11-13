"""
Applet Manager Service
Handles enabling/disabling workspace applets
"""
from app import db
from app.models.workspace_applet import WorkspaceApplet


def get_enabled_applets(tenant_id):
    """
    Get list of enabled applet keys for a workspace

    Args:
        tenant_id: ID of the tenant/workspace

    Returns:
        List of enabled applet keys (e.g., ['crm', 'projects', 'tasks'])
    """
    enabled = WorkspaceApplet.query.filter_by(
        tenant_id=tenant_id,
        is_enabled=True
    ).all()

    return [applet.applet_key for applet in enabled]


def is_applet_enabled(tenant_id, applet_key):
    """
    Check if a specific applet is enabled for a workspace

    Args:
        tenant_id: ID of the tenant/workspace
        applet_key: Key of the applet to check (e.g., 'crm', 'projects')

    Returns:
        Boolean indicating if applet is enabled
    """
    applet = WorkspaceApplet.query.filter_by(
        tenant_id=tenant_id,
        applet_key=applet_key
    ).first()

    # If not found, assume enabled for backward compatibility
    if not applet:
        return True

    return applet.is_enabled


def enable_applet(tenant_id, applet_key):
    """
    Enable an applet for a workspace

    Args:
        tenant_id: ID of the tenant/workspace
        applet_key: Key of the applet to enable

    Returns:
        Boolean indicating success
    """
    # Validate applet key
    if applet_key not in WorkspaceApplet.get_all_applet_keys():
        return False

    applet = WorkspaceApplet.query.filter_by(
        tenant_id=tenant_id,
        applet_key=applet_key
    ).first()

    if applet:
        # Update existing record
        applet.is_enabled = True
    else:
        # Create new record
        applet = WorkspaceApplet(
            tenant_id=tenant_id,
            applet_key=applet_key,
            is_enabled=True
        )
        db.session.add(applet)

    db.session.commit()
    return True


def disable_applet(tenant_id, applet_key):
    """
    Disable an applet for a workspace
    Note: This hides the applet but preserves all data

    Args:
        tenant_id: ID of the tenant/workspace
        applet_key: Key of the applet to disable

    Returns:
        Boolean indicating success
    """
    # Validate applet key
    if applet_key not in WorkspaceApplet.get_all_applet_keys():
        return False

    applet = WorkspaceApplet.query.filter_by(
        tenant_id=tenant_id,
        applet_key=applet_key
    ).first()

    if applet:
        # Update existing record
        applet.is_enabled = False
    else:
        # Create new record (disabled)
        applet = WorkspaceApplet(
            tenant_id=tenant_id,
            applet_key=applet_key,
            is_enabled=False
        )
        db.session.add(applet)

    db.session.commit()
    return True


def initialize_applets_for_tenant(tenant_id, applet_keys=None, enabled=True):
    """
    Initialize applets for a new workspace/tenant

    Args:
        tenant_id: ID of the tenant/workspace
        applet_keys: List of applet keys to initialize (defaults to all)
        enabled: Whether the applets should be enabled or disabled

    Returns:
        Number of applets initialized
    """
    if applet_keys is None:
        applet_keys = WorkspaceApplet.get_all_applet_keys()

    count = 0
    for applet_key in applet_keys:
        # Check if already exists
        existing = WorkspaceApplet.query.filter_by(
            tenant_id=tenant_id,
            applet_key=applet_key
        ).first()

        if not existing:
            applet = WorkspaceApplet(
                tenant_id=tenant_id,
                applet_key=applet_key,
                is_enabled=enabled
            )
            db.session.add(applet)
            count += 1

    db.session.commit()
    return count


def get_applet_status(tenant_id):
    """
    Get status of all applets for a workspace

    Args:
        tenant_id: ID of the tenant/workspace

    Returns:
        Dict mapping applet keys to their enabled status and metadata
    """
    all_keys = WorkspaceApplet.get_all_applet_keys()
    status = {}

    for applet_key in all_keys:
        applet_info = WorkspaceApplet.get_applet_info(applet_key)
        enabled = is_applet_enabled(tenant_id, applet_key)

        status[applet_key] = {
            'enabled': enabled,
            'name': applet_info['name'],
            'description': applet_info['description'],
            'icon': applet_info['icon']
        }

    return status
