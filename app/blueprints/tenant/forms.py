from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional, Length


class InviteUserForm(FlaskForm):
    """Invite user to tenant form"""
    email = StringField('Email Address', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address')
    ])
    role = SelectField('Role', choices=[
        ('member', 'Member - Can participate and use features'),
        ('admin', 'Admin - Can manage departments and settings'),
        ('owner', 'Owner - Full access including billing')
    ], default='member')
    submit = SubmitField('Send Invitation')


class WorkspaceContextForm(FlaskForm):
    """Edit workspace custom context form"""
    custom_context = TextAreaField('Workspace Context', validators=[
        Optional(),
        Length(max=10000, message='Context must be less than 10,000 characters')
    ])
    submit = SubmitField('Save Context')
