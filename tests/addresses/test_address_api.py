from datetime import datetime

from app.users.models.role import Role
from app.users.models.user import User
from app.models.address import Address
from tests import BaseTestCase, db

class TestAddressAPI(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(id=10, name='admin')
        self.user = User(id=10, username='user1_test_address_api', email='user_test_address_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True)
        self.admin = User(username='root_test_address_api', email='root_test_address_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
                enabled=True, roles=[admin_role])
        self.try_add_entities([ self.user, self.admin, admin_role ])

    def try_admin_operation(self, operation):
        '''
        Superseeds base method to add class-specific user and admin credentials
        '''
        return super().try_admin_operation(
            operation,
            'user1_test_address_api', '1', 'root_test_address_api', '1')

    def test_get_address(self):
        self.try_add_entities([
           Address(id=123, name='Address_1', zip=11111, address_1='address01', address_2='address02')
        ])
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/admin/address'))
        self.assertEqual(len(res.json), 1)

    def test_save_address(self):
        gen_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Address(id=gen_id, name='Address_1', zip='11111', address_1='address01', address_2='address02')
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/address/{gen_id}',
            json={'zip': '22222'})
        )
        self.assertEqual(res.status_code, 200)
        address = Address.query.get(gen_id)
        self.assertEqual(address.zip, '22222')

        res = self.client.post(f'/api/v1/admin/address/{gen_id}',
            json={'zip': '22222@'})
        self.assertEqual(res.status_code, 400)

    
    def test_delete_address(self):
        gen_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Address(id=gen_id, name='Address_1', zip='11111', address_1='address01', address_2='address02')
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f'/api/v1/admin/address/{gen_id}')
        )
        self.assertEqual(res.status_code, 200)
        address = Address.query.get(gen_id)
        self.assertEqual(address, None)
    