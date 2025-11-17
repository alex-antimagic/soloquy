"""
Forms for website builder
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, URL, Regexp


class WebsiteSettingsForm(FlaskForm):
    """Form for website settings"""
    title = StringField('Website Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    is_published = BooleanField('Publish Website')
    is_indexable = BooleanField('Allow Search Engines', default=True)
    google_analytics_property_id = StringField('Google Analytics Property ID', validators=[Optional(), Length(max=50)])


class WebsitePageForm(FlaskForm):
    """Form for creating/editing pages"""
    page_type = SelectField('Page Type',
                           choices=[('home', 'Home Page'),
                                   ('blog', 'Blog Post'),
                                   ('landing', 'Landing Page'),
                                   ('custom', 'Custom Page')],
                           validators=[DataRequired()])
    slug = StringField('URL Slug', validators=[DataRequired(),
                                               Length(max=200),
                                               Regexp('^[a-z0-9-]+$', message='Only lowercase letters, numbers, and hyphens allowed')])
    title = StringField('Page Title', validators=[DataRequired(), Length(max=200)])
    meta_description = TextAreaField('Meta Description', validators=[Optional(), Length(max=500)])
    is_published = BooleanField('Publish Page')


class WebsiteThemeForm(FlaskForm):
    """Form for theme customization"""
    theme_name = SelectField('Theme Preset',
                            choices=[('professional', 'Professional'),
                                    ('creative', 'Creative'),
                                    ('minimal', 'Minimal'),
                                    ('bold', 'Bold'),
                                    ('elegant', 'Elegant')],
                            validators=[DataRequired()])
    primary_color = StringField('Primary Color', validators=[DataRequired(),
                                                             Length(max=7),
                                                             Regexp('^#[0-9A-Fa-f]{6}$', message='Must be hex color (e.g. #667eea)')])
    secondary_color = StringField('Secondary Color', validators=[DataRequired(),
                                                                 Length(max=7),
                                                                 Regexp('^#[0-9A-Fa-f]{6}$')])
    background_color = StringField('Background Color', validators=[DataRequired(),
                                                                   Length(max=7),
                                                                   Regexp('^#[0-9A-Fa-f]{6}$')])
    text_color = StringField('Text Color', validators=[DataRequired(),
                                                       Length(max=7),
                                                       Regexp('^#[0-9A-Fa-f]{6}$')])
    heading_font = StringField('Heading Font', validators=[DataRequired(), Length(max=100)])
    body_font = StringField('Body Font', validators=[DataRequired(), Length(max=100)])


class WebsiteFormBuilderForm(FlaskForm):
    """Form for creating website forms"""
    name = StringField('Form Name', validators=[DataRequired(), Length(max=200)])
    form_key = StringField('Form Key', validators=[DataRequired(),
                                                   Length(max=100),
                                                   Regexp('^[a-z0-9-]+$', message='Only lowercase letters, numbers, and hyphens allowed')])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    success_message = TextAreaField('Success Message', validators=[DataRequired(), Length(max=500)])
    redirect_url = StringField('Redirect URL (optional)', validators=[Optional(), URL()])
    notification_emails = StringField('Notification Emails (comma-separated)', validators=[Optional()])
    create_lead = BooleanField('Create Lead in CRM', default=True)
    require_captcha = BooleanField('Require CAPTCHA', default=True)
    is_active = BooleanField('Active', default=True)
