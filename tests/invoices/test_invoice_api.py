from datetime import datetime

from app.models import Country, Order, OrderProduct, Product, Role, User
from app.invoices.models import Invoice, InvoiceItem
from tests import BaseTestCase, db

class TestInvoiceClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(id=10, name='admin')
        self.try_add_entities([
            User(username='root_test_invoice_api', email='root_test_invoice_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
                enabled=True, roles=[admin_role]),
            User(id=10, username='user1_test_invoice_api', email='user_test_invoice_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            admin_role,
            Country(id='c1', name='country1'),
            Order(id='test-invoice-api-1')
        ])

    def try_admin_operation(self, operation):
        '''
        Superseeds base method to add class-specific user and admin credentials
        '''
        return super().try_admin_operation(
            operation,
            'user1_test_invoice_api', '1', 'root_test_invoice_api', '1')
    
    def test_create_invoice(self):
        self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/invoice/new'))
        res = self.client.post('/api/v1/admin/invoice/new', json={
            'order_ids': ['test-invoice-api-1']
        })
        self.assertEqual(res.json['invoice_id'], 'INV-2020-09-0001')

    def test_get_invoices(self):
        db.session.add_all([
            Invoice(id='INV-2020-00-00',
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0)),
            InvoiceItem(invoice_id='INV-2020-00-00', product_id='0001', price=10, quantity=1),
            Order(id=__name__ + '-1', invoice_id='INV-2020-00-00', country='c1'),
            Product(id='0001', name='Product 1')
        ])
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice'))
        res = self.client.get('/api/v1/admin/invoice/INV-2020-00-00')
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0], {
            'address': None,
            'country': 'c1',
            'customer': None,
            'id': 'INV-2020-00-00',
            'invoice_items': [{
                'product_id': '0001',
                'name': 'Product 1',
                'price': 10,
                'quantity': 1,
                'subtotal': 10
            }],
            'orders': [__name__ + '-1'],
            'phone': None,
            'total': 10,
            'weight': 0,
            'when_changed': '2020-01-01 01:00:00',
            'when_created': '2020-01-01 01:00:00'
        })

    def test_get_invoice_excel(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/0/excel/0'))

    def test_get_invoice_cumulative_excel(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/excel?invoices[0]=INV-2020-00-00&invoices[0]=INV-2020-00-00'))
        res = self.client.get('/api/v1/admin/invoice/excel?invoices[0]=INV-2020-00-00&invoices[0]=INV-2020-00-00')
        self.assertTrue(res.status_code, 200)
