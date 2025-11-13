"""
Workspace Applet Model
Tracks which applets (modules) are enabled for each workspace/tenant
"""
from datetime import datetime
from app import db


class WorkspaceApplet(db.Model):
    """Model for workspace applet enable/disable state"""

    __tablename__ = 'workspace_applets'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    applet_key = db.Column(db.String(50), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    tenant = db.Relationship('Tenant', backref=db.backref('applets', lazy='dynamic', cascade='all, delete-orphan'))

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'applet_key', name='uq_tenant_applet'),
    )

    def __repr__(self):
        return f'<WorkspaceApplet {self.applet_key} for Tenant {self.tenant_id}: {"enabled" if self.is_enabled else "disabled"}>'

    # Available applet keys
    APPLET_KEYS = {
        'crm': {
            'name': 'CRM',
            'description': 'Manage companies, contacts, deals, and leads',
            'icon': 'briefcase'
        },
        'projects': {
            'name': 'Projects',
            'description': 'Task management and Kanban boards',
            'icon': 'kanban'
        },
        'support': {
            'name': 'Support',
            'description': 'Customer support ticketing system',
            'icon': 'headset'
        },
        'tasks': {
            'name': 'Tasks',
            'description': 'Personal and team task management',
            'icon': 'check-square'
        },
        'chat': {
            'name': 'Chat',
            'description': 'Team messaging and AI agent conversations',
            'icon': 'chat-dots'
        },
        'integrations': {
            'name': 'Integrations',
            'description': 'Connect third-party tools and services',
            'icon': 'plug'
        }
    }

    @classmethod
    def get_all_applet_keys(cls):
        """Get list of all available applet keys"""
        return list(cls.APPLET_KEYS.keys())

    @classmethod
    def get_applet_info(cls, applet_key):
        """Get metadata for an applet"""
        return cls.APPLET_KEYS.get(applet_key)
