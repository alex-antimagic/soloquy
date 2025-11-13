from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from app.models.user import User
from app.utils.input_validators import validate_password_strength


class LoginForm(FlaskForm):
    """Login form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    """User registration form"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[Length(max=80)])
    last_name = StringField('Last Name', validators=[Length(max=80)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

    def validate_email(self, email):
        """Check if email is already registered"""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email or login.')

    def validate_password(self, password):
        """Check password meets security requirements"""
        is_valid, error = validate_password_strength(password.data)
        if not is_valid:
            raise ValidationError(error)
