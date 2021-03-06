from tests import BaseTestCase, db
from app.users.models.role import Role
from app.users.models.user import User
from app.orders.models import Order, Subcustomer, Suborder
from app.products.models import Product

class TestSubcustomersApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_subcustomers_api', email='root_test_subcustomers_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True)
        self.admin = User(username='root_test_subcustomers_api', email='root_test_subcustomers_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Product(id='0000', name='Test product', price=10, weight=10)        
        ])

    def test_create_subcustomer(self):
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/order/subcustomer', json={
                "name":"Subcustomer1",
                "username":"s1",
                "password":"p1",
        }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Subcustomer.query.count(), 1)
        res = self.client.post('/api/v1/admin/order/subcustomer', json={
                "name":"Subcustomer2",
                "username":"s1",
                "password":"p1",
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/admin/order/subcustomer', json={})
        self.assertEqual(res.status_code, 400)

    def test_save_subcustomer(self):
        subcustomer1 = Subcustomer(name='S1', username='s1', password='p1')
        subcustomer2 = Subcustomer(name='S2', username='s2', password='p1')
        self.try_add_entities([subcustomer1, subcustomer2])
        res = self.try_admin_operation(
            lambda: self.client.post('/api/v1/admin/order/subcustomer/999', json={}))
        self.assertEqual(res.status_code, 404)
        
        res = self.client.post(f'/api/v1/admin/order/subcustomer/{subcustomer1.id}', json={
                "name":"Subcustomer1",
                "username":"s11",
                "password":"p1",
        })
        self.assertEqual(res.status_code, 200)
        res = self.client.post(f'/api/v1/admin/order/subcustomer/{subcustomer1.id}', json={
                "name":"Subcustomer2",
                "username":"s2",
                "password":"p1",
        })
        self.assertEqual(res.status_code, 409)

    def test_delete_subcustomer(self):
        subcustomer1 = Subcustomer(name='S1', username='s1', password='p1')
        subcustomer2 = Subcustomer(name='S2', username='s2', password='p2')
        order = Order()
        self.try_add_entities([
            subcustomer1, subcustomer2,
            Suborder(order=order, subcustomer=subcustomer2)
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f'/api/v1/admin/order/subcustomer/{subcustomer1.id}')
        )
        self.assertEqual(Subcustomer.query.count(), 1)
        res = self.client.delete(f'/api/v1/admin/order/subcustomer/{subcustomer2.id}')
        self.assertEqual(res.status_code, 409)
        res = self.client.delete('/api/v1/admin/order/subcustomer/999')
        self.assertEqual(res.status_code, 404)
