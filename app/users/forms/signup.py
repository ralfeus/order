from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Regexp

def _is_email_valid(form, field):
    validate_email = Email(message='Enter a valid email.')
    if field.data:
        validate_email(form, field)

class SignupForm(FlaskForm):
    """User Sign-up Form."""
    username = StringField('User name', validators=[DataRequired()])
    email = StringField('Email', validators=[_is_email_valid])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm = PasswordField('Confirm Your Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')])
    phone = StringField('Phone', validators=[DataRequired()])
    atomy_id = StringField('Atomy ID', validators=[Regexp(r'(S|\d\d{7})?')])
    submit = SubmitField('Register')
