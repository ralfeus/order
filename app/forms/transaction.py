from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import DecimalField, FileField, RadioField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange

from app.currencies.models import Currency

class TransactionForm(FlaskForm):
    '''
    Product creation and editing form
    '''
    amount_original = DecimalField('Transaction amount', places=2, validators=[
        NumberRange(min=0, message='Amount must be positive number')])
    currency_code = RadioField('Transaction currency', validators=[DataRequired()])
    order_id = SelectField('Order ID to pay for')
    payment_method = SelectField('Payment method',
        choices=[('Wire transfer', 'Wire transfer'), ('PayPal', 'PayPal')]
    )
    evidence = FileField('Upload the transaction proof', validators=[
        FileAllowed(['jpg', 'jpeg', 'pdf', 'png'],
            message="Only acceptable files are JPEG, PNG and PDF")])
    submit = SubmitField('Create transaction request')
