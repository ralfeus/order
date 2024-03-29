from unittest.mock import MagicMock, patch
from tests import BaseTestCase
from flask import current_app

from app import db
from app.addresses.models import Address
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
import app.products.models as pr
import app.purchase.models as p
from app.purchase.models.vendors.atomy_quick import AtomyQuick
from app.users.models import Role, User
from exceptions import AtomyLoginError

def get_json(url, **kwargs):
    items = [{
                'id': '000000',
                'materialCode': '000000',
                'optionType': { 'value': 'none' },
                'flags': ['none']
            }]
    url_parts = { 
        'address/createAddress': {'item': {}},
        'address/getDeliveryAddressList': {'items': []},
        'address/updateAddress':{'result': '200', 'item': {}},
        'atms/search': {
            'totalCount': 1,
            'items': items
        },
        'businessTaxbill/createBusinessTaxbill': {'item': {'id': '000'}},
        'businessTaxbill/getBusinessTaxbillList': {'items': [{'businessNumber': '000000000'}]},
        'cart/addToCart' : {'items': [{
            'success': True, 'entryId': 123, 'statusCode': 'ErrorStatus'}]},
        'cart/createCart': {'items': [{'cartId': 'CartID_XXX'}]},
        'cart/getBuynowCart': {
            'item': {
                'deliveryInfos': [{'id': '0'}],
                'paymentType': {'configs': [{'id': '0'}]},
                'totalPrice': 10
            }},
        'cart/updateCart': {'result': '200'},
        'order/validateCheckout': {'result': '200'},
        'order/placeOrder': {'result': '200','item':{'id': 'ItemID_XXX'}},
        'order/getOrderList': {'result': '200', 'items': []},
        'order/getOrderResult': {'item':{
            'paymentTransactions': [{'info': {'accountNumber': 'AccountID_XXX'}}],
            'totalPrice': 100
        }},
        'payment/getDepositDeadline': {'item': {'deadline': ''}},
        'product/options': {
            'item': {
                'option': {
                    'productOptions': [{
                        'materialCode': '000000'
                    }]
                }
            }
        },
        'product/simpleList': {'items': [{}]}
    }
    
    for url_part, response in url_parts.items():
        if url_part in url:
            return response

class TestPurchaseOrdersVendorAtomyQuick(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_po_api', email='root_test_po_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_po_api', email='root_test_po_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            pr.Product(id='000000', name='Test product', price=10, weight=10)
        ])


    @patch('app.purchase.models.vendors.atomy_quick.invoke_curl', 
           MagicMock(return_value=('{"result": "200"}', '')))
    @patch('app.purchase.models.vendors.atomy_quick:AtomyQuick._AtomyQuick__login',
           MagicMock(return_value=['atomySvcJWT=token']))
    @patch('app.purchase.models.vendors.atomy_quick.get_json',
           MagicMock(side_effect=get_json))
    def test_post_purchase_order(self):
        subcustomer = Subcustomer(username='s1', password='p1')
        order = Order()
        so = Suborder(order)
        op = OrderProduct(suborder=so, product_id='000000', quantity=10)
        company = p.Company(bank_id='32')
        po = p.PurchaseOrder(so, customer=subcustomer, company=company,
                             contact_phone='010-1234-1234', 
                             payment_phone='010-1234-1234',
                             address=Address(address_1='', address_2=''))
        self.try_add_entities([
            order, so, op, po, company
        ])
        po = p.PurchaseOrder.query.get(po.id)
        res = AtomyQuick(config=current_app.config).post_purchase_order(po)
        self.assertEqual(res[0].payment_account, 'AccountID_XXX')
