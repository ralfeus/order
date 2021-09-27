import re
from app import db

from . import PaymentMethod

class PayPal(PaymentMethod):
    __mapper_args__ = {'polymorphic_identity': 'paypal'}
    
    def __init__(self):
        self.name = 'PayPal'
    
    def execute_payment(self, payment):
        from app.settings.models.setting import Setting
        client_id = Setting.query.get('payment.paypal.client_id')
        client_id = client_id.value if client_id is not None else None
        client_id = client_id not in (None, '')
        return {'url': '%s/paypal' % payment.id} if client_id else None

#if response is not None:
#         # Check to see if the API request was successfully received and acted upon
#         if response.messages.resultCode == "Ok":
#             # Since the API request was successful, look for a transaction response
#             # and parse it to display the results of authorizing the card
#             if hasattr(response.transactionResponse, 'messages') is True:
#                 print(
#                     'Successfully created transaction with Transaction ID: %s'
#                     % response.transactionResponse.transId)
#                 print('Transaction Response Code: %s' %
#                       response.transactionResponse.responseCode)
#                 print('Message Code: %s' %
#                       response.transactionResponse.messages.message[0].code)
#                 print('Description: %s' % response.transactionResponse.
#                       messages.message[0].description)
#             else:
#                 print('Failed Transaction.')
#                 if hasattr(response.transactionResponse, 'errors') is True:
#                     print('Error Code:  %s' % str(response.transactionResponse.
#                                                   errors.error[0].errorCode))
#                     print(
#                         'Error message: %s' %
#                         response.transactionResponse.errors.error[0].errorText)
#         # Or, print errors if the API request wasn't successful
#         else:
#             print('Failed Transaction.')
#             if hasattr(response, 'transactionResponse') is True and hasattr(
#                     response.transactionResponse, 'errors') is True:
#                 print('Error Code: %s' % str(
#                     response.transactionResponse.errors.error[0].errorCode))
#                 print('Error message: %s' %
#                       response.transactionResponse.errors.error[0].errorText)
#             else:
#                 print('Error Code: %s' %
#                       response.messages.message[0]['code'].text)
#                 print('Error message: %s' %
#                       response.messages.message[0]['text'].text)
#     else:
#         print('Null Response.')

#     return response
