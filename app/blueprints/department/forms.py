from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, FloatField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, ValidationError, NumberRange, Optional
from app.models.department import Department
from flask import g


class DepartmentForm(FlaskForm):
    """Department creation/edit form"""
    name = StringField('Department Name', validators=[
        DataRequired(),
        Length(min=2, max=255, message='Department name must be between 2 and 255 characters')
    ])
    slug = StringField('Slug', validators=[
        DataRequired(),
        Length(min=2, max=100, message='Slug must be between 2 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[Length(max=500)])
    color = StringField('Color', validators=[DataRequired()], default='#6C757D')
    icon = StringField('Icon', validators=[Length(max=50)])
    submit = SubmitField('Create Department')

    def validate_slug(self, slug):
        """Check if slug is unique within the tenant"""
        if g.current_tenant:
            existing = Department.query.filter_by(
                tenant_id=g.current_tenant.id,
                slug=slug.data.lower()
            ).first()
            if existing:
                raise ValidationError('A department with this slug already exists in your workspace.')


class AgentForm(FlaskForm):
    """Agent editing form"""
    # Identity
    name = StringField('Agent Name', validators=[
        DataRequired(),
        Length(min=2, max=255, message='Agent name must be between 2 and 255 characters')
    ])
    description = TextAreaField('Role/Description', validators=[
        Optional(),
        Length(max=500, message='Description must be less than 500 characters')
    ])
    avatar_url = StringField('Avatar Filename', validators=[
        Optional(),
        Length(max=255)
    ])

    # Instructions
    system_prompt = TextAreaField('Custom Instructions', validators=[
        Optional(),
        Length(max=10000, message='Instructions must be less than 10,000 characters')
    ])

    # Configuration
    model = SelectField('Claude Model', choices=[
        ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5 (Fastest - Near-frontier intelligence)'),
        ('claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5 (Smartest - Complex agents & coding)'),
        ('claude-opus-4-1-20250805', 'Claude Opus 4.1 (Exceptional - Specialized reasoning)')
    ], default='claude-haiku-4-5-20251001')

    temperature = FloatField('Temperature', validators=[
        Optional(),
        NumberRange(min=0.0, max=1.0, message='Temperature must be between 0 and 1')
    ], default=1.0)

    max_tokens = IntegerField('Max Tokens', validators=[
        Optional(),
        NumberRange(min=256, max=8192, message='Max tokens must be between 256 and 8192')
    ], default=4096)

    is_active = BooleanField('Agent Enabled', default=True)

    submit = SubmitField('Save Changes')
