'''
Tests of warehouse functionality API
'''
from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User
from app.products.models.product import Product
from app.modules.warehouse.models.warehouse import Warehouse, WarehouseProduct

class TestWarehouseApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_warehouse_api', email='root_test_warehouse_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_warehouse_api', email='root_test_warehouse_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role
        ])

    def test_create_warehouse(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/warehouse', json={
                "name":"Warehouse1",
        }))
        self.assertEqual(res.status_code, 200)
        warehouses = Warehouse.query.all()
        self.assertEqual(len(warehouses), 1)

    def test_get_warehouse(self):
        self.try_add_entities([
            Warehouse(name='W1')
        ])
        res = self.try_admin_operation(lambda:
            self.client.get('/api/v1/admin/warehouse')
        )
        self.assertEqual(len(res.json), 1)

    def test_save_warehouse(self):
        self.try_add_entities([
            Warehouse(name='W1')
        ])
        warehouse = Warehouse.query.first()
        self.try_admin_operation(lambda:
            self.client.post(f'/api/v1/admin/warehouse/{warehouse.id}', json={
                'name': 'W2'
            })
        )
        self.assertEqual(Warehouse.query.first().name, 'W2')

    def delete_warehouse(self):       
        self.try_add_entities([
            Warehouse(name='W1')
        ])
        warehouse = Warehouse.query.first()
        res = self.try_admin_operation(lambda:
            self.client.delete(f'/api/v1/admin/warehouse/{warehouse.id}')
        )
        self.assertEqual(Warehouse.query.count(), 0)

    def test_create_warehouse_product(self):
        self.try_add_entities([
            Warehouse(name='W1'),
            Product(id='0000', name='P1')
        ])
        w = Warehouse.query.first()
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/warehouse/{w.id}/product',
                json={
                    "product_id": "0000",
                    'quantity': 10
        }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(w.products), 1)

    def test_get_warehouse_products(self):
        w = Warehouse(name='W1')
        self.try_add_entities([
            w, Product(id='0000', name='P1')
        ])
        self.try_add_entities([
            WarehouseProduct(warehouse_id=w.id, product_id='0000', quantity=1)
        ])
        res = self.try_admin_operation(lambda:
            self.client.get(f'/api/v1/admin/warehouse/{w.id}/product')
        )
        self.assertEqual(len(res.json), 1)

    def test_save_warehouse_product(self):
        w = Warehouse(name='W1')
        self.try_add_entities([
            w, Product(id='0000', name='P1')
        ])
        self.try_add_entities([
            WarehouseProduct(warehouse_id=w.id, product_id='0000', quantity=1)
        ])
        self.try_admin_operation(lambda:
            self.client.post(f'/api/v1/admin/warehouse/{w.id}/product/0000', json={
                'product_id': '0000',
                'quantity': 2
            })
        )
        self.assertEqual(
            WarehouseProduct.query.filter_by(
                warehouse_id=w.id, product_id='0000').first().quantity,
            2)

    def delete_warehouse_product(self):   
        w = Warehouse(name='W1')
        self.try_add_entities([
            w, Product(id='0000', name='P1')
        ])
        self.try_add_entities([
            WarehouseProduct(warehouse_id=w.id, product_id='0000', quantity=1)
        ])
        self.try_admin_operation(lambda:
            self.client.delete(f'/api/v1/admin/warehouse/{w.id}/product/0000')
        )
        self.assertEqual(len(w.products), 0)
