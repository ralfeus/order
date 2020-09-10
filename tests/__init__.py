from unittest import TestCase

from app import create_app, db
from app.config import TestConfig

app = create_app(TestConfig)
app.app_context().push()

class BaseTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        db.session.execute('pragma foreign_keys=on')

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.maxDiff = None


    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def try_admin_operation(self, operation, user_name, user_password, admin_name, admin_password):
        res = operation()
        self.assertEqual(res.status_code, 302)
        res = self.login(user_name, user_password)
        res = operation()
        self.assertEqual(res.status_code, 302)
        self.logout()
        self.login(admin_name, admin_password)
        return operation()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ))

    def logout(self):
        return self.client.get('/logout')

    def try_add_entity(self, entity):
        try:
            db.session.add(entity)
            db.session.commit()
        except Exception as e:
            print(e)
            db.session.rollback()

    def try_add_entities(self, entities):
        for entity in entities:
            self.try_add_entity(entity)