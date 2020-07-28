from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo

class SignupForm(FlaskForm):
    """User Sign-up Form."""
    username = StringField('User name', validators=[DataRequired()])
    email = StringField('Email', validators=[Email(message='Enter a valid email.'), DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm = PasswordField('Confirm Your Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Register')
