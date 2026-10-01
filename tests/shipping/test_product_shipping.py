'''Tests of shipping methods restricted by products of several vendors'''
from tests import BaseTestCase, db
from app.products.models import Product
from app.shipping.models.shipping import Shipping


class TestProductShipping(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        self.any_shipping = Shipping(id=1, name='Any')
        self.special_shipping = Shipping(id=2, name='Special')
        self.try_add_entities([self.any_shipping, self.special_shipping])
        self.try_add_entities([
            # No restriction - shippable by any shipping
            Product(id='0001', vendor='Atomy', name='Atomy 1'),
            Product(id='0001', vendor='AtomyAza', name='AZA 1',
                    available_shipping=[self.special_shipping]),
            Product(id='Z9', vendor='AtomyAza', name='AZA Z9'),
        ])

    def _can_ship(self, shipping_id, products):
        return db.session.get(Shipping, shipping_id).can_ship(None, 0, products)

    def test_product_keys(self):
        self.assertTrue(self._can_ship(1, ['Atomy:0001']))
        self.assertFalse(self._can_ship(1, ['AtomyAza:0001']))
        self.assertTrue(self._can_ship(2, ['AtomyAza:0001']))
        self.assertTrue(self._can_ship(1, ['Atomy:0001', 'AtomyAza:Z9']))
        self.assertFalse(self._can_ship(1, ['Atomy:0001', 'AtomyAza:0001']))

    def test_product_codes(self):
        self.assertTrue(self._can_ship(1, ['Z9']))
        # Ambiguous code is shippable only if all its products are
        self.assertFalse(self._can_ship(1, ['0001']))
        self.assertTrue(self._can_ship(2, ['0001']))
        # Code without leading zeros
        self.assertTrue(self._can_ship(2, ['1']))

    def test_unknown_products(self):
        self.assertFalse(self._can_ship(1, ['nonexistent']))
        self.assertFalse(self._can_ship(1, ['Atomy:Z9']))

    def test_no_products(self):
        self.assertTrue(self._can_ship(1, []))
