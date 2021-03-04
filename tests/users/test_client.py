from flask_security import current_user
from tests import BaseTestCase, db

from app.users.models.user import User

def login(client, username='user1', password='1'):
    return client.post('/login', data={
        'username': username,
        'password': password
    })

def logout(client):
    return client.get('/logout')

class TestClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        self.user = User(username='user1', email='user@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True)
        self.try_add_entities([
            self.user,
            User(username='user2', email='user2@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=False)
        ])

    def tearDown(self):
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
            res = self.client.post('/users/signup', data={
                'username': 'user3',
                'password': '1',
                'confirm': '1',
                'phone': '1',
                'email': 'test@email.com'
            })
            res = login(self.client, 'user3', '1')
            self.assertEqual(res.status_code, 200)
            user3 = User.query.filter_by(username='user3').first()
            user3.enabled = True
            db.session.commit()
            res = login(self.client, 'user3', '1')
            self.assertEqual(current_user.username, 'user3')
