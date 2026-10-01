'''
Tests of warehouse products of several vendors having the same product ID
'''
from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User
from app.products.models.product import Product
from app.modules.warehouse.models.warehouse import Warehouse, WarehouseProduct

PASSWORD_HASH = 'pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576'


class TestWarehouseVendors(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        admin_role = Role(name='admin')
        self.admin = User(username='admin_warehouse_vendors', email='a@name.com',
                          password_hash=PASSWORD_HASH, enabled=True, roles=[admin_role])
        self.warehouse = Warehouse(id=1, name='W1')
        self.try_add_entities([
            self.admin, admin_role, self.warehouse,
            Product(id='0001', vendor='Atomy', name='Atomy 1'),
            Product(id='0001', vendor='AtomyAza', name='AZA 1'),
        ])
        self.url = '/api/v1/admin/warehouse/1/product'
        self.login(self.admin.username, '1')

    def _stock(self):
        db.session.expire_all()
        return {wp.product.key: wp.quantity for wp in WarehouseProduct.query}

    def _add(self, product_key, quantity):
        res = self.client.post(self.url, json={'product_id': product_key, 'quantity': quantity})
        self.assertEqual(res.status_code, 200)
        return res

    def test_create_by_key(self):
        res = self._add('AtomyAza:0001', 5)
        self.assertEqual(res.json['data'][0]['product_key'], 'AtomyAza:0001')
        self.assertEqual(res.json['data'][0]['product_vendor'], 'AtomyAza')
        self._add('Atomy:0001', 7)
        self.assertEqual(self._stock(), {'AtomyAza:0001': 5, 'Atomy:0001': 7})

    def test_create_by_ambiguous_code(self):
        res = self.client.post(self.url, json={'product_id': '0001', 'quantity': 1})
        self.assertIn('fieldErrors', res.json)
        self.assertIn('AtomyAza:0001', str(res.json['fieldErrors']))
        self.assertEqual(self._stock(), {})

    def test_get_edit_delete_by_key(self):
        self._add('AtomyAza:0001', 5)
        self._add('Atomy:0001', 7)
        res = self.client.get(f'{self.url}/AtomyAza:0001')
        self.assertEqual([p['product_key'] for p in res.json['data']], ['AtomyAza:0001'])

        # UI sends whole row including product key
        res = self.client.post(f'{self.url}/AtomyAza:0001',
                               json={'product_id': 'AtomyAza:0001', 'quantity': 9})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._stock(), {'AtomyAza:0001': 9, 'Atomy:0001': 7})

        res = self.client.delete(f'{self.url}/AtomyAza:0001')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._stock(), {'Atomy:0001': 7})

    def test_ambiguous_code_in_url(self):
        self._add('AtomyAza:0001', 5)
        self.assertEqual(self.client.post(
            f'{self.url}/0001', json={'product_id': 'AtomyAza:0001', 'quantity': 9}).status_code,
            409)
        self.assertEqual(self.client.delete(f'{self.url}/0001').status_code, 409)

    def test_not_existing_product_in_url(self):
        self._add('AtomyAza:0001', 5)
        self.assertEqual(self.client.delete(f'{self.url}/Atomy:0001').status_code, 404)
        self.assertEqual(self.client.post(
            f'{self.url}/Atomy:0001', json={'product_id': 'Atomy:0001', 'quantity': 1}).status_code,
            404)
        self.assertEqual(self.client.get(f'{self.url}/Atomy:0001').json, {'data': []})
