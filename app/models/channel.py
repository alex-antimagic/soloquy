"""
Channel model for custom chat channels (Slack-style)
"""
from app import db
from datetime import datetime

# Channel members association table
channel_members = db.Table('channel_members',
    db.Column('channel_id', db.Integer, db.ForeignKey('channels.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('added_at', db.DateTime, nullable=False, default=datetime.utcnow)
)

# Channel agents association table
channel_agents = db.Table('channel_agents',
    db.Column('channel_id', db.Integer, db.ForeignKey('channels.id'), primary_key=True),
    db.Column('agent_id', db.Integer, db.ForeignKey('agents.id'), primary_key=True),
    db.Column('added_at', db.DateTime, nullable=False, default=datetime.utcnow)
)


class Channel(db.Model):
    __tablename__ = 'channels'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Multi-tenancy
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # Channel Info
    name = db.Column(db.String(100), nullable=False)  # e.g., "general", "random", "marketing"
    slug = db.Column(db.String(100), nullable=False, index=True)  # URL-friendly name
    description = db.Column(db.Text)
    is_private = db.Column(db.Boolean, default=False)  # Private channels require membership
    is_archived = db.Column(db.Boolean, default=False)

    # Department Association (optional - for agent context)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True, index=True)

    # Creator
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship('Tenant', backref=db.backref('channels', lazy='dynamic'))
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref=db.backref('created_channels', lazy='dynamic'))
    department = db.relationship('Department', backref=db.backref('channels', lazy='dynamic'))
    members = db.relationship('User', secondary=channel_members, backref=db.backref('channels', lazy='dynamic'))
    agents = db.relationship('Agent', secondary=channel_agents, backref=db.backref('channels', lazy='dynamic'))

    # Messages will use the existing Message model with channel_id

    def __repr__(self):
        return f'<Channel #{self.name}>'

    @property
    def display_name(self):
        """Display name with # prefix"""
        return f"#{self.name}"

    @property
    def member_count(self):
        """Get number of members"""
        if not self.is_private:
            # Public channels: all tenant members
            return len(self.tenant.get_members())
        # Private channels: explicit members only
        return len(self.members)

    @property
    def is_department_channel(self):
        """Check if this channel is associated with a department"""
        return self.department_id is not None

    def get_associated_agents(self):
        """Get AI agents associated with this channel (via department + explicit)"""
        agents = list(self.agents)  # Explicitly added agents

        # Add department agents if channel is associated with a department
        if self.department:
            dept_agents = self.department.get_agents()
            # Avoid duplicates
            for agent in dept_agents:
                if agent not in agents:
                    agents.append(agent)

        return agents

    def can_user_access(self, user):
        """Check if a user can access this channel"""
        # Public channels: all tenant members can access
        if not self.is_private:
            return user in self.tenant.get_members()
        # Private channels: must be explicit member
        return user in self.members

    def add_member(self, user):
        """Add a user to this channel (for private channels)"""
        if user not in self.members:
            self.members.append(user)
            return True
        return False

    def remove_member(self, user):
        """Remove a user from this channel"""
        if user in self.members:
            self.members.remove(user)
            return True
        return False

    def add_agent(self, agent):
        """Add an agent to this channel"""
        if agent not in self.agents:
            self.agents.append(agent)
            return True
        return False

    def remove_agent(self, agent):
        """Remove an agent from this channel"""
        if agent in self.agents:
            self.agents.remove(agent)
            return True
        return False

    def get_members(self):
        """Get all members who can access this channel"""
        if not self.is_private:
            # Public channels: return all tenant members
            return self.tenant.get_members()
        # Private channels: return explicit members
        return self.members
