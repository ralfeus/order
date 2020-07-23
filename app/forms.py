'''
Contains application's forms
'''
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import Product

class SignupForm(FlaskForm):
    """User Sign-up Form."""
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Length(min=6), Email(message='Enter a valid email.'), DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, message='Select a stronger password.')])
    confirm = PasswordField('Confirm Your Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username')
    email = StringField('Email', validators=[Length(min=6), Email(message='Enter a valid email.'), DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class ProductForm(FlaskForm):
    '''
    Product creation and editing form
    '''
    id = StringField('Product code', validators=[DataRequired()])
    name = StringField('Original name')
    name_english = StringField('English name')
    name_russian = StringField('Russian name')
    weight = IntegerField('Unit weight in grams', validators=[DataRequired()])
    price = IntegerField('Unit price', validators=[DataRequired()])
    points = IntegerField('Unit points', validators=[DataRequired()])
    submit = SubmitField('Create product')

    def validate_id(form, field):
        product = Product.query.get(field.data)
        if product:
            raise ValidationError("Such product code exists")
