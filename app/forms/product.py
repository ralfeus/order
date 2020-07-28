from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError

from app.models import Product

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
