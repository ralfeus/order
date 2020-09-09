import unittest

from app import create_app, db
from app.config import TestConfig
from app.models import Role, User

app = create_app(TestConfig)
app.app_context().push()

def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ))

def logout(client):
    return client.get('/logout')

class TestInvoiceClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # db.session.execute('pragma foreign_keys=on')
        pass

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        db.create_all()
        
        admin_role = Role(id=10, name='admin')
        try:
            db.session.add_all([
                User(id=0, username='root', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True, roles=[admin_role]),
                User(id=10, username='user1', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True),
                User(id=20, username='user2', email='user@name.com',
                    password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                    enabled=True),
                admin_role
            ])
            db.session.commit()
        except:
            db.session.rollback()

    def try_admin_operation(self, operation):
        res = operation()
        self.assertTrue(res.status_code, 302)
        login(self.client, 'user1', '1')
        res = operation()
        self.assertTrue(res.status_code, 403)
        logout(self.client)
        login(self.client, 'root', '1')
        return operation()
    
    def test_get_invoice(self):
        self.try_admin_operation(
            lambda: self.client.get('/admin/invoice/1'))