from datetime import datetime
from flask_security import current_user
import unittest

from app import create_app, db, security
from app.config import TestConfig

app = create_app(TestConfig)
app.app_context().push()
from app.models import Currency, Order, OrderProduct, OrderProductStatusEntry, Product, \
        Shipping, ShippingRate, User

def login(client, username='user1', password='1'):
    return client.post('/login', data={
        'username': username,
        'password': password
    })

class TestClient(unittest.TestCase):
    @classmethod
    # def setUpClass(cls):
    #     db.session.execute('pragma foreign_keys=on')

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

        db.create_all()
            
        # entities = [
        #     User(
        #         username='user1',
        #         password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
        #         enabled=True)
        # ]
        # db.session.add_all(entities)
        # db.session.commit()
        security.datastore.create_user(username='user1', password='1')

    def tearDown(self):
        if self._ctx is not None:
            self._ctx.pop()
        db.session.remove()
        db.drop_all()

    def test_login(self):
        with self.client:
            res = login(self.client, 'user1', '1')
            self.assertEqual(current_user.username, 'user1')

if __name__ == '__main__':
    unittest.main()
