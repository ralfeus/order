'''
Tests of invoices with products of several vendors having the same product ID
'''
from datetime import datetime

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.models import Country
from app.invoices.models import Invoice, InvoiceItem
from app.invoices.routes.api import get_invoice_order_products
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.users.models.role import Role
from app.users.models.user import User

PASSWORD_HASH = 'pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576'


class TestInvoiceVendors(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        admin_role = Role(name='admin')
        self.admin = User(username='admin_invoice_vendors', email='a@name.com',
                          password_hash=PASSWORD_HASH, enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.admin, admin_role,
            Currency(code='USD', rate=1),
            Country(id='c1', name='country1'),
            Product(id='0001', vendor='Atomy', name='Atomy 1', weight=1),
            Product(id='0001', vendor='AtomyAza', name='AZA 1', weight=2),
            Product(id='Z9', vendor='AtomyAza', name='AZA Z9', weight=3),
        ])
        self.invoice = Invoice(currency_code='USD', user=self.admin, when_created=datetime.now())
        self.try_add_entities([self.invoice])

    def test_saved_items_of_same_id_arent_merged(self):
        self.try_add_entities([
            InvoiceItem(invoice=self.invoice, product_id='Atomy:0001', price=10, quantity=1),
            InvoiceItem(invoice=self.invoice, product_id='AtomyAza:0001', price=10, quantity=2),
            InvoiceItem(invoice=self.invoice, product_id='AtomyAza:0001', price=10, quantity=3),
        ])
        items = self.invoice.to_dict(details=True)['invoice_items']
        self.assertEqual(sorted((i['product_key'], i['quantity']) for i in items),
                         [('Atomy:0001', 1), ('AtomyAza:0001', 2), ('AtomyAza:0001', 3)])
        # Items are combined for invoice document
        rows = get_invoice_order_products(self.invoice)
        self.assertEqual(sorted((r['id'], r['name'], r['quantity']) for r in rows),
                         [('0001', 'AZA 1', 5), ('0001', 'Atomy 1', 1)])

    def test_items_from_orders_arent_merged(self):
        order = Order(user=self.admin, invoice=self.invoice, country_id='c1')
        suborder = Suborder(order=order)
        self.try_add_entities([order, suborder])
        aza_suborder = Suborder(order=order)
        self.try_add_entities([aza_suborder])
        self.try_add_entities([
            OrderProduct(suborder=suborder, product_id='Atomy:0001', price=10, quantity=1),
            OrderProduct(suborder=aza_suborder, product_id='AtomyAza:0001', price=10, quantity=2),
        ])
        db.session.expire_all()
        invoice = db.session.get(Invoice, self.invoice.id)
        items = invoice.to_dict(details=True)['invoice_items']
        self.assertEqual(sorted((i['product_key'], i['quantity']) for i in items),
                         [('Atomy:0001', 1), ('AtomyAza:0001', 2)])
        self.assertEqual(invoice.to_dict()['weight'], 1 + 2 * 2)
        rows = get_invoice_order_products(invoice)
        self.assertEqual(len(rows), 2)

    def test_admin_change_invoice_item_product(self):
        item = InvoiceItem(invoice=self.invoice, product_id='Atomy:0001', price=10, quantity=1)
        self.try_add_entities([item])
        url = f'/api/v1/admin/invoice/{self.invoice.id}/item/{item.id}'
        self.login(self.admin.username, '1')
        res = self.client.post(url, json={'product_id': 'AtomyAza:0001'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['product_key'], 'AtomyAza:0001')
        res = self.client.post(url, json={'product_id': 'Z9'})
        self.assertEqual(res.json['product_key'], 'AtomyAza:Z9')
        res = self.client.post(url, json={'product_id': '0001'})
        self.assertEqual(res.status_code, 409)
        res = self.client.post(url, json={'product_id': 'nonexistent'})
        self.assertEqual(res.status_code, 404)
        db.session.expire_all()
        self.assertEqual(db.session.get(InvoiceItem, item.id).product.key, 'AtomyAza:Z9')

    def test_admin_create_invoice_item(self):
        self.login(self.admin.username, '1')
        res = self.client.post(f'/api/v1/admin/invoice/{self.invoice.id}/item/new',
                               json={'product_id': 'AtomyAza:0001', 'price': 1, 'quantity': 1})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['product_key'], 'AtomyAza:0001')
