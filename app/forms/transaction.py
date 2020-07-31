from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import DecimalField, FileField, RadioField, SubmitField
from wtforms.validators import DataRequired, NumberRange

from app.models import Currency

class TransactionForm(FlaskForm):
    '''
    Product creation and editing form
    '''
    amount_original = DecimalField('Transaction amount', places=2, validators=[
        NumberRange(min=0, message='Amount must be positive number')])
    currency_code = RadioField('Transaction currency', validators=[DataRequired()])
    proof = FileField('Upload the transaction proof', validators=[
        FileAllowed(['jpg', 'jpeg', 'pdf', 'png'],
            message="Only acceptable files are JPEG, PNG and PDF")])
    submit = SubmitField('Create transaction request')
