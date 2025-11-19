"""
Department Membership Model
Associates users with departments for access control
"""
from datetime import datetime
from app import db


class DepartmentMembership(db.Model):
    """
    User membership in departments
    Enables department-level access control
    """
    __tablename__ = 'department_memberships'

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    department = db.relationship('Department', back_populates='memberships')
    user = db.relationship('User', backref=db.backref('department_memberships', lazy='dynamic'))

    # Unique constraint: one membership per user per department
    __table_args__ = (
        db.UniqueConstraint('department_id', 'user_id', name='uq_dept_user_membership'),
        db.Index('ix_department_memberships_department_id', 'department_id'),
        db.Index('ix_department_memberships_user_id', 'user_id'),
    )

    def __repr__(self):
        return f'<DepartmentMembership user_id={self.user_id} department_id={self.department_id}>'
