from app.purchase.models.company import Company
from app.users.models.role import Role
from app.users.models.user import User

from tests import BaseTestCase, db

class TestCompanyClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(id=10, name='admin')
        self.try_add_entities([
            User(id=0, username='root', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True, roles=[admin_role]),
            User(id=10, username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            User(id=20, username='user2', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True),
            admin_role,
            Company()
        ])

    def try_admin_operation(self, operation):
        return super().try_admin_operation(operation, 'user1', '1', 'root', '1')
    
    def test_get_company(self):
        self.try_add_entities([
            Company(id=125)
        ])
        self.try_admin_operation(
            lambda: self.client.get('/admin/companies/')
            )