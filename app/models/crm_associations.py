from datetime import datetime
from app import db


# Deal-Contact many-to-many
deal_contacts = db.Table('deal_contacts',
    db.Column('deal_id', db.Integer, db.ForeignKey('deals.id'), primary_key=True),
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True),
    db.Column('role', db.String(50)),  # decision_maker, influencer, champion, blocker
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)


# Deal-Task many-to-many (existing tasks can be linked to deals)
deal_tasks = db.Table('deal_tasks',
    db.Column('deal_id', db.Integer, db.ForeignKey('deals.id'), primary_key=True),
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)
