'''
Tests of suborder holding products of a single vendor
'''
from tests import BaseTestCase, db
from app.models import Country
from app.orders.models.order import Order
from app.orders.models.order_product import OrderProduct
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.shipping.models.shipping import PostponeShipping, Shipping, ShippingRate
from app.users.models.user import User
from common.exceptions import OrderError


class TestSuborderVendor(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        self.user = User(username='user_suborder_vendor', email='u@name.com',
                         password_hash='', enabled=True)
        self.atomy = Product(id='0001', vendor='Atomy', name='Atomy 1', price=10, weight=10)
        self.atomy2 = Product(id='0002', vendor='Atomy', name='Atomy 2', price=10, weight=10)
        self.aza = Product(id='0001', vendor='AtomyAza', name='AZA 1', price=20, weight=10)
        self.aza2 = Product(id='Z9', vendor='AtomyAza', name='AZA Z9', price=30, weight=10)
        self.try_add_entities([
            self.user, self.atomy, self.atomy2, self.aza, self.aza2,
            Country(id='c1', name='country1'),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=100),
        ])
        self.order = Order(user=self.user, shipping_method_id=1, country_id='c1')
        self.try_add_entity(self.order)
        self.suborder = Suborder(order=self.order, subcustomer=Subcustomer())
        self.try_add_entity(self.suborder)

    def test_new_suborder_is_atomy(self):
        self.assertEqual(self.suborder.vendor, 'Atomy')

    def test_empty_suborder_takes_vendor_of_first_product(self):
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.aza2, quantity=1))
        self.assertEqual(self.suborder.vendor, 'AtomyAza')
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.aza, quantity=1))
        db.session.expire_all()
        self.assertEqual(db.session.get(Suborder, self.suborder.id).vendor, 'AtomyAza')

    def test_product_of_other_vendor_is_rejected(self):
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.atomy, quantity=1))
        with self.assertRaises(OrderError):
            OrderProduct(suborder=self.suborder, product=self.aza, quantity=1)

    def test_product_given_by_id_is_checked(self):
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.aza, quantity=1))
        with self.assertRaises(OrderError):
            OrderProduct(suborder=self.suborder, product_id='Atomy:0002', quantity=1)

    def test_product_before_suborder_is_checked(self):
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.atomy, quantity=1))
        with self.assertRaises(OrderError):
            OrderProduct(product=self.aza, suborder=self.suborder, quantity=1)

    def test_change_product_to_other_vendor(self):
        op1 = OrderProduct(suborder=self.suborder, product=self.atomy, quantity=1)
        op2 = OrderProduct(suborder=self.suborder, product=self.atomy2, quantity=1)
        self.try_add_entities([op1, op2])
        with self.assertRaises(OrderError):
            op1.product = self.aza
        # The only product of the suborder can be changed to any vendor
        db.session.delete(op2)
        db.session.flush()
        db.session.refresh(self.suborder)
        op1.product = self.aza
        self.assertEqual(self.suborder.vendor, 'AtomyAza')

    def test_suborder_vendor_set_beforehand_is_kept(self):
        '''Order saving sets vendor before replacing products'''
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.atomy, quantity=1))
        self.suborder.vendor = 'AtomyAza'
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.aza, quantity=1))
        self.assertEqual(self.suborder.vendor, 'AtomyAza')

    def test_postpone_goes_to_suborder_of_same_vendor(self):
        self.try_add_entity(PostponeShipping())
        atomy_op = OrderProduct(suborder=self.suborder, product=self.atomy, quantity=1)
        aza_suborder = Suborder(order=self.order, subcustomer=self.suborder.subcustomer)
        aza_op = OrderProduct(suborder=aza_suborder, product=self.aza, quantity=1)
        self.try_add_entities([atomy_op, aza_suborder, aza_op])
        postponed_atomy = atomy_op.postpone()
        db.session.flush()
        postponed_aza = aza_op.postpone()
        db.session.flush()
        self.assertEqual(postponed_atomy.suborder.order_id, postponed_aza.suborder.order_id)
        self.assertNotEqual(postponed_atomy.suborder_id, postponed_aza.suborder_id)
        self.assertEqual(postponed_atomy.suborder.vendor, 'Atomy')
        self.assertEqual(postponed_aza.suborder.vendor, 'AtomyAza')

    def test_rejected_product_isnt_in_suborder(self):
        self.try_add_entity(OrderProduct(suborder=self.suborder, product=self.atomy, quantity=1))
        with self.assertRaises(OrderError):
            OrderProduct(suborder=self.suborder, product=self.aza, quantity=1)
        self.assertEqual([op.product for op in self.suborder.order_products], [self.atomy])
