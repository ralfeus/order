'''Tests of the Product model identity: vendor-qualified keys
and global lookup by code'''
from tests import BaseTestCase, db
from app.products.models.product import AmbiguousProductError, Product


class TestProductModel(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        db.session.add_all([
            Product(id='000123', vendor='Atomy', name='Atomy 123'),
            Product(id='123', vendor='AtomyAza', name='AZA 123'),
            Product(id='000456', vendor='Atomy', name='Atomy 456'),
            Product(id='695221:4540592', vendor='AtomyAza', name='AZA option'),
        ])
        db.session.commit()

    def test_default_vendor(self):
        db.session.add(Product(id='000789', name='No vendor'))
        db.session.commit()
        self.assertEqual(Product.get_by_key('Atomy:000789').name, 'No vendor')

    def test_key(self):
        product = Product.get_by_key('AtomyAza:695221:4540592')
        self.assertEqual(product.name, 'AZA option')
        self.assertEqual(product.key, 'AtomyAza:695221:4540592')

    def test_get_by_key_not_found(self):
        self.assertIsNone(Product.get_by_key('AtomyAza:000456'))
        self.assertIsNone(Product.get_by_key('Atomy:456'))
        self.assertIsNone(Product.get_by_key('Unknown:000123'))
        self.assertIsNone(Product.get_by_key('000456'))
        self.assertIsNone(Product.get_by_key(''))

    def test_find_by_code_single_match(self):
        self.assertEqual(Product.find_by_code('000456').key, 'Atomy:000456')
        self.assertEqual(Product.find_by_code('456').key, 'Atomy:000456')

    def test_find_by_code_ambiguous(self):
        with self.assertRaises(Exception) as context:
            Product.find_by_code('123')
        self.assertIn('Atomy:000123', str(context.exception))
        self.assertIn('AtomyAza:123', str(context.exception))

    def test_find_by_code_with_key(self):
        self.assertEqual(Product.find_by_code('AtomyAza:123').name, 'AZA 123')
        self.assertEqual(Product.find_by_code('Atomy:123').name, 'Atomy 123')
        self.assertEqual(Product.find_by_code('AtomyAza:695221:4540592').name,
                         'AZA option')

    def test_find_by_code_bare_code_with_colon(self):
        self.assertEqual(Product.find_by_code('695221:4540592').key,
                         'AtomyAza:695221:4540592')

    def test_find_by_code_not_found(self):
        self.assertIsNone(Product.find_by_code('999'))
        self.assertIsNone(Product.find_by_code('Atomy:000999'))

    def test_get_product_by_id_is_global_lookup(self):
        self.assertEqual(Product.get_product_by_id('456').key, 'Atomy:000456')
        with self.assertRaises(Exception):
            Product.get_product_by_id('123')

    def test_resolve(self):
        '''Exact lookup by key or product ID (no leading zeros stripping)'''
        self.assertEqual(Product.resolve('Atomy:000123').name, 'Atomy 123')
        self.assertEqual(Product.resolve('000123').name, 'Atomy 123')
        self.assertEqual(Product.resolve('123').name, 'AZA 123')
        self.assertEqual(Product.resolve('AtomyAza:695221:4540592').name, 'AZA option')
        self.assertEqual(Product.resolve('695221:4540592').name, 'AZA option')
        self.assertIsNone(Product.resolve('456'))
        self.assertIsNone(Product.resolve('Atomy:123'))
        self.assertIsNone(Product.resolve(''))
        self.assertIsNone(Product.resolve(None))

    def test_key_of_unknown_vendor_is_a_code(self):
        db.session.add(Product(id='Unknown:1', name='Weird code'))
        db.session.commit()
        self.assertIsNone(Product.get_by_key('Unknown:1'))
        self.assertEqual(Product.resolve('Unknown:1').name, 'Weird code')
        self.assertEqual(Product.find_by_code('Unknown:1').name, 'Weird code')

    def test_same_id_in_different_vendors(self):
        db.session.add(Product(id='000456', vendor='AtomyAza', name='AZA 456'))
        db.session.commit()
        self.assertEqual(Product.get_by_key('Atomy:000456').name, 'Atomy 456')
        self.assertEqual(Product.get_by_key('AtomyAza:000456').name, 'AZA 456')
        with self.assertRaises(AmbiguousProductError):
            Product.resolve('000456')
        self.assertEqual(Product.resolve('AtomyAza:000456').name, 'AZA 456')

    def test_references_respect_vendor(self):
        from app.invoices.models.invoice import Invoice
        from app.invoices.models.invoice_item import InvoiceItem
        from app.modules.warehouse.models.warehouse import Warehouse, WarehouseProduct
        from app.orders.models.order_product import OrderProduct
        from app.shipping.models.shipping import Shipping
        from app.currencies.models import Currency
        invoice = Invoice(currency_code='USD')
        db.session.add_all([
            Currency(code='USD', rate=1),
            Product(id='000456', vendor='AtomyAza', name='AZA 456'),
            invoice,
            Warehouse(id=1, name='W1'),
            Shipping(id=1, name='S1')
        ])
        db.session.commit()
        db.session.add_all([
            InvoiceItem(invoice=invoice, product_id='AtomyAza:000456', price=1, quantity=1),
            InvoiceItem(invoice=invoice, product_id='Atomy:000456', price=1, quantity=1),
            WarehouseProduct(warehouse_id=1, product_id='AtomyAza:000456', quantity=1),
            WarehouseProduct(warehouse_id=1, product_id='Atomy:000456', quantity=2),
        ])
        Product.get_by_key('AtomyAza:000456').available_shipping = \
            [db.session.get(Shipping, 1)]
        db.session.commit()
        db.session.expire_all()

        items = InvoiceItem.query.order_by(InvoiceItem.id).all()
        self.assertEqual([i.product.key for i in items],
                         ['AtomyAza:000456', 'Atomy:000456'])
        self.assertEqual([(i.product_id, i.product_vendor) for i in items],
                         [('000456', 'AtomyAza'), ('000456', 'Atomy')])
        stock = {wp.product.key: wp.quantity for wp in WarehouseProduct.query}
        self.assertEqual(stock, {'AtomyAza:000456': 1, 'Atomy:000456': 2})
        self.assertEqual(len(Product.get_by_key('AtomyAza:000456').available_shipping), 1)
        self.assertEqual(len(Product.get_by_key('Atomy:000456').available_shipping), 0)
        order_product = OrderProduct(product_id='AtomyAza:000456', quantity=1)
        self.assertEqual(order_product.product.key, 'AtomyAza:000456')
        with self.assertRaises(AmbiguousProductError):
            OrderProduct(product_id='000456', quantity=1)

    def test_shipping_invoice_item_without_product(self):
        from app.invoices.models.invoice import Invoice
        from app.invoices.models.invoice_item import InvoiceItem
        from app.currencies.models import Currency
        invoice = Invoice(currency_code='USD')
        db.session.add_all([Currency(code='USD', rate=1), invoice])
        db.session.commit()
        db.session.add(InvoiceItem(invoice=invoice, product_id='SHIPPING',
                                   price=10, quantity=1))
        db.session.commit()
        item = InvoiceItem.query.first()
        self.assertEqual(item.product_id, 'SHIPPING')
        self.assertIsNone(item.product_vendor)
        self.assertIsNone(item.product)

    def test_to_dict(self):
        result = Product.get_by_key('AtomyAza:123').to_dict()
        self.assertEqual(result['id'], '123')
        self.assertEqual(result['vendor'], 'AtomyAza')
        self.assertEqual(result['key'], 'AtomyAza:123')
