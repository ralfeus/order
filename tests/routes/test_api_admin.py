from datetime import datetime
from flask_login import login_user
import unittest
from werkzeug.exceptions import Forbidden

from app import create_app, db
from app.config import TestConfig
import app.routes.api_admin as test_target

app = create_app(TestConfig)
app.app_context().push()

from app.models import Order, User
admin = User(id=0, username='admin')
user = User(id=999, username="User")

class TestAdminApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.session.execute('pragma foreign_keys=on')

    def setUp(self):
        db.create_all()
        db.session.add_all([
            User(id=1, username='User1', email='user@name.com', password_hash='#', enabled=True),
            User(id=2, username='User2', email='user@name.com', password_hash='#', enabled=True),
            Order(id=1, user_id=2)
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_delete_user(self):
        with app.test_request_context():
            login_user(user, remember=True)
            with self.assertRaises(Forbidden):
                test_target.delete_user(1)
            login_user(admin)
            res = test_target.delete_user(2)
            self.assertEqual(res.status, '409 CONFLICT')
