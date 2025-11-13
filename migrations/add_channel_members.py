"""
Add channel members table for managing private channel membership
"""
from app import db

# Create the association table
channel_members = db.Table('channel_members',
    db.Column('channel_id', db.Integer, db.ForeignKey('channels.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('added_at', db.DateTime, nullable=False, default=db.func.now()),
    db.Column('added_by_id', db.Integer, db.ForeignKey('users.id'))
)
