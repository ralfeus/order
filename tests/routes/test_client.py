from flask_security import current_user
import unittest

from app import create_app, db, security
from app.config import TestConfig

app = create_app(TestConfig)
app.app_context().push()

def login(client, username='user1', password='1'):
    return client.post('/login', data={
        'username': username,
        'password': password
    })

def logout(client):
    return client.get('/logout')

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

        security.datastore.create_user(username='user1', password='1', enabled=True)
        security.datastore.create_user(username='user2', password='1', active=False)

    def tearDown(self):
        if self._ctx is not None:
            self._ctx.pop()
        db.session.remove()
        db.drop_all()

    def test_login(self):
        with self.client:
            res = login(self.client, 'user1', '1')
            self.assertEqual(res.status_code, 302)
            self.assertEqual(current_user.username, 'user1')
            logout(self.client)
            res = login(self.client, 'user2', '1')
            self.assertEqual(res.status_code, 200)

    def test_signup(self):
        with self.client:
            res = self.client.post('/signup', data={
                'username': 'user3',
                'password': '1',
                'email': 'test@email.com'
            })
            res = login(self.client, 'user3', '1')
            self.assertEqual(res.status_code, 200)
            user3 = security.datastore.get_user('user3')
            security.datastore.activate_user(user3)
            res = login(self.client, 'user3', '1')
            self.assertEqual(current_user.username, 'user3')

if __name__ == '__main__':
    unittest.main()
