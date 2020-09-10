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
        self.try_add_entities([
            Product(id='0001', name='Product 1', weight=10),
            Invoice(id='INV-2020-00-00',
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0)),
            InvoiceItem(invoice_id='INV-2020-00-00', product_id='0001', price=10, quantity=1),
            Order(id=__name__ + '-1', invoice_id='INV-2020-00-00', country='c1')
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
                'id': 1,
                'invoice_id': 'INV-2020-00-00',
                'product_id': '0001',
                'product': 'Product 1',
                'price': 10,
                'weight': 10,
                'quantity': 1,
                'subtotal': 10,
                'when_created': None,
                'when_changed': None
            }],
            'orders': [__name__ + '-1'],
            'phone': None,
            'total': 10,
            'weight': 10,
            'when_changed': '2020-01-01 01:00:00',
            'when_created': '2020-01-01 01:00:00'
        })

    def test_get_old_invoice(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Product(id=gen_id, name='Product 1', weight=10),
            Invoice(id=gen_id,
                    when_created=datetime(2020, 1, 1, 1, 0, 0),
                    when_changed=datetime(2020, 1, 1, 1, 0, 0)),
            Order(id=gen_id, invoice_id=gen_id, country='c1'),
            OrderProduct(order_id=gen_id, product_id=gen_id, price=10, quantity=1)
        ])
        res = self.try_admin_operation(
            lambda: self.client.get(f'/api/v1/admin/invoice/{gen_id}'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json), 1)
        self.assertEqual(res.json[0], {
            'address': None,
            'country': 'c1',
            'customer': None,
            'id': gen_id,
            'invoice_items': [{
                'id': 1,
                'invoice_id': gen_id,
                'product_id': gen_id,
                'product': 'Product 1',
                'price': 10,
                'weight': 10,
                'quantity': 1,
                'subtotal': 10,
                'when_created': None,
                'when_changed': None
            }],
            'orders': [gen_id],
            'phone': None,
            'total': 10,
            'weight': 10,
            'when_changed': '2020-01-01 01:00:00',
            'when_created': '2020-01-01 01:00:00'
        })


    def test_get_invoice_excel(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Invoice(id=gen_id),
            InvoiceItem(invoice_id=gen_id, product_id=gen_id, price=1, quantity=1),
            Product(id=gen_id, weight=1)
        ])
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/0/excel/0.0'))

    def test_get_invoice_cumulative_excel(self):
        self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/invoice/excel?invoices[0]=INV-2020-00-00&invoices[0]=INV-2020-00-00'))
        res = self.client.get('/api/v1/admin/invoice/excel?invoices[0]=INV-2020-00-00&invoices[0]=INV-2020-00-00')
        self.assertTrue(res.status_code, 200)

    def test_create_invoice_item(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id),
            OrderProduct(order_id=gen_id, product_id=gen_id, price=10, quantity=10),
            Product(id=gen_id, name='Product 1'),
            Invoice(id=gen_id, order_id=gen_id)
        ])
        self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/invoice/{gen_id}/item/new')
        )
        res = self.client.post(f'/api/v1/admin/invoice/{gen_id}/item/new',
            json={'invoice_id': gen_id, 'product_id': gen_id, 'price': 10, 'quantity': 10})
        self.assertTrue(res.status_code, 200)
    
    def test_save_invoice_item(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id),
            OrderProduct(order_id=gen_id, product_id=gen_id, price=10, quantity=10),
            Product(id=gen_id, name='Product 1'),
            Invoice(id=gen_id, order_id=gen_id),
            InvoiceItem(id=10, invoice_id=gen_id, product_id=gen_id, price=10, quantity=10)
        ])
        self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/invoice/{gen_id}/item/10')
        )
        res = self.client.post(f'/api/v1/admin/invoice/{gen_id}/item/10', 
            json={'price': 20})
        self.assertEqual(res.status_code, 200)
        invoice_item = InvoiceItem.query.get(10)
        self.assertEqual(invoice_item.price, 20)
    
    def test_delete_invoice_item(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id),
            OrderProduct(order_id=gen_id, product_id=gen_id, price=10, quantity=10),
            Product(id=gen_id, name='Product 1'),
            Invoice(id=gen_id, order_id=gen_id),
            InvoiceItem(id=10, invoice_id=gen_id, product_id=gen_id, price=10, quantity=10)
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f'/api/v1/admin/invoice/{gen_id}/item/10')
        )
        self.assertEqual(res.status_code, 200)
        invoice_item = InvoiceItem.query.get(10)
        self.assertEqual(invoice_item, None)