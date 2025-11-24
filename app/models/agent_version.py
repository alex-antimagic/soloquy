"""
Agent Version Model

Tracks complete version history for AI agents with automatic change detection.
Enables rollback, diff comparison, and version tagging.
"""
from datetime import datetime
from app import db
import json


class AgentVersion(db.Model):
    """Complete snapshot of agent configuration at a specific point in time"""
    __tablename__ = 'agent_versions'

    # Primary keys and relationships
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False, index=True)

    # Version metadata
    version_number = db.Column(db.Integer, nullable=False)  # Auto-incremented per agent
    is_active_version = db.Column(db.Boolean, default=False, nullable=False)  # Currently live version
    version_tag = db.Column(db.String(50))  # Optional: "stable", "beta", "production", "backup"

    # Change tracking
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    change_summary = db.Column(db.String(500))  # Auto-generated description of changes
    change_type = db.Column(db.String(50))  # 'initial', 'update', 'rollback', 'import'
    changes_diff = db.Column(db.Text)  # JSON array of specific field changes

    # Complete snapshot of agent configuration at this version
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))
    system_prompt = db.Column(db.Text)
    model = db.Column(db.String(50))  # claude-haiku-4-5, claude-sonnet-4-5, claude-opus-4-5
    temperature = db.Column(db.Float, default=0.7)
    max_tokens = db.Column(db.Integer)

    # Integration access flags (security sensitive)
    enable_quickbooks = db.Column(db.Boolean, default=False, nullable=False)
    enable_gmail = db.Column(db.Boolean, default=False, nullable=False)
    enable_outlook = db.Column(db.Boolean, default=False, nullable=False)
    enable_google_drive = db.Column(db.Boolean, default=False, nullable=False)
    enable_website_builder = db.Column(db.Boolean, default=False, nullable=False)
    enable_file_generation = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    agent = db.relationship('Agent', back_populates='versions')
    changed_by = db.relationship('User', foreign_keys=[changed_by_id])

    # Constraints
    __table_args__ = (
        db.UniqueConstraint('agent_id', 'version_number', name='unique_version_per_agent'),
        db.Index('ix_agent_versions_active', 'agent_id', 'is_active_version'),
    )

    def to_dict(self, include_diff=False):
        """Convert version to dictionary"""
        data = {
            'id': self.id,
            'agent_id': self.agent_id,
            'version_number': self.version_number,
            'is_active_version': self.is_active_version,
            'version_tag': self.version_tag,
            'changed_by': {
                'id': self.changed_by.id,
                'name': self.changed_by.full_name,
                'email': self.changed_by.email
            } if self.changed_by else None,
            'change_summary': self.change_summary,
            'change_type': self.change_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,

            # Configuration snapshot
            'configuration': {
                'name': self.name,
                'description': self.description,
                'avatar_url': self.avatar_url,
                'system_prompt': self.system_prompt,
                'model': self.model,
                'temperature': self.temperature,
                'max_tokens': self.max_tokens,
                'integrations': {
                    'quickbooks': self.enable_quickbooks,
                    'gmail': self.enable_gmail,
                    'outlook': self.enable_outlook,
                    'google_drive': self.enable_google_drive,
                    'website_builder': self.enable_website_builder,
                    'file_generation': self.enable_file_generation
                }
            }
        }

        if include_diff and self.changes_diff:
            try:
                data['changes'] = json.loads(self.changes_diff)
            except:
                data['changes'] = []

        return data

    def get_changes(self):
        """Get parsed changes diff"""
        if not self.changes_diff:
            return []
        try:
            return json.loads(self.changes_diff)
        except:
            return []

    def get_display_summary(self):
        """Get user-friendly version summary"""
        if self.change_summary:
            return self.change_summary

        if self.change_type == 'initial':
            return "Initial version"
        elif self.change_type == 'rollback':
            return f"Rolled back to previous configuration"
        elif self.change_type == 'import':
            return "Imported from file"
        else:
            return "Updated configuration"

    @staticmethod
    def create_from_agent(agent, changed_by_user, version_number=None, change_summary=None,
                         change_type='update', previous_version=None):
        """
        Create a new version snapshot from current agent state

        Args:
            agent: Agent instance to snapshot
            changed_by_user: User making the change
            version_number: Optional explicit version number (otherwise auto-increment)
            change_summary: Optional manual summary (otherwise auto-generated)
            change_type: Type of change (initial, update, rollback, import)
            previous_version: Previous AgentVersion for diff generation

        Returns:
            New AgentVersion instance (not yet committed)
        """
        from app.models.agent import Agent  # Avoid circular import

        # Auto-increment version number if not provided
        if version_number is None:
            max_version = db.session.query(db.func.max(AgentVersion.version_number))\
                .filter_by(agent_id=agent.id).scalar()
            version_number = (max_version or 0) + 1

        # Auto-generate change summary if not provided
        if not change_summary and previous_version:
            change_summary = AgentVersion._generate_change_summary(previous_version, agent)
        elif not change_summary:
            change_summary = "Initial version" if version_number == 1 else "Updated configuration"

        # Generate diff if we have a previous version
        changes_diff_json = None
        if previous_version:
            changes_diff_json = json.dumps(
                AgentVersion._generate_diff(previous_version, agent)
            )

        # Create version snapshot
        version = AgentVersion(
            agent_id=agent.id,
            version_number=version_number,
            is_active_version=False,  # Will be set to True after deactivating others
            version_tag=None,
            changed_by_id=changed_by_user.id,
            change_summary=change_summary,
            change_type=change_type,
            changes_diff=changes_diff_json,

            # Snapshot all agent fields
            name=agent.name,
            description=agent.description,
            avatar_url=agent.avatar_url,
            system_prompt=agent.system_prompt,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            enable_quickbooks=agent.enable_quickbooks,
            enable_gmail=agent.enable_gmail,
            enable_outlook=agent.enable_outlook,
            enable_google_drive=agent.enable_google_drive,
            enable_website_builder=agent.enable_website_builder,
            enable_file_generation=agent.enable_file_generation
        )

        return version

    @staticmethod
    def _generate_change_summary(old_version, new_agent):
        """Auto-generate human-readable summary of what changed"""
        changes = []

        # Check name change
        if old_version.name != new_agent.name:
            changes.append(f"renamed to '{new_agent.name}'")

        # Check description
        if old_version.description != new_agent.description:
            changes.append("updated description")

        # Check system prompt
        if old_version.system_prompt != new_agent.system_prompt:
            changes.append("updated system prompt")

        # Check model change
        if old_version.model != new_agent.model:
            old_model_display = (old_version.model or '').replace('claude-', '').replace('-4-5', '').title()
            new_model_display = (new_agent.model or '').replace('claude-', '').replace('-4-5', '').title()
            changes.append(f"changed model from {old_model_display} to {new_model_display}")

        # Check temperature
        if old_version.temperature != new_agent.temperature:
            changes.append(f"adjusted temperature to {new_agent.temperature}")

        # Check max_tokens
        if old_version.max_tokens != new_agent.max_tokens:
            changes.append(f"set max tokens to {new_agent.max_tokens}")

        # Check integrations
        integration_changes = []
        integrations = [
            ('quickbooks', 'QuickBooks'),
            ('gmail', 'Gmail'),
            ('outlook', 'Outlook'),
            ('google_drive', 'Google Drive'),
            ('website_builder', 'Website Builder')
        ]

        for field, display_name in integrations:
            old_val = getattr(old_version, f'enable_{field}')
            new_val = getattr(new_agent, f'enable_{field}')
            if old_val != new_val:
                action = "enabled" if new_val else "disabled"
                integration_changes.append(f"{action} {display_name}")

        if integration_changes:
            changes.extend(integration_changes)

        # Format final summary
        if not changes:
            return "Minor configuration update"

        summary = ", ".join(changes)
        return summary[:500]  # Truncate to field limit

    @staticmethod
    def _generate_diff(old_version, new_agent):
        """Generate detailed diff of specific field changes"""
        diff = []

        # Compare each field
        fields = [
            ('name', 'Name'),
            ('description', 'Description'),
            ('system_prompt', 'System Prompt'),
            ('model', 'Model'),
            ('temperature', 'Temperature'),
            ('max_tokens', 'Max Tokens'),
        ]

        for field, display_name in fields:
            old_val = getattr(old_version, field)
            new_val = getattr(new_agent, field)

            if old_val != new_val:
                diff.append({
                    'field': field,
                    'display_name': display_name,
                    'old_value': str(old_val) if old_val is not None else None,
                    'new_value': str(new_val) if new_val is not None else None,
                    'type': 'text' if field in ['system_prompt', 'description'] else 'simple'
                })

        # Check integrations
        integrations = [
            ('enable_quickbooks', 'QuickBooks Access'),
            ('enable_gmail', 'Gmail Access'),
            ('enable_outlook', 'Outlook Access'),
            ('enable_google_drive', 'Google Drive Access'),
            ('enable_website_builder', 'Website Builder Access'),
            ('enable_file_generation', 'File Generation')
        ]

        for field, display_name in integrations:
            old_val = getattr(old_version, field)
            new_val = getattr(new_agent, field)

            if old_val != new_val:
                diff.append({
                    'field': field,
                    'display_name': display_name,
                    'old_value': old_val,
                    'new_value': new_val,
                    'type': 'boolean',
                    'security_sensitive': True
                })

        return diff
