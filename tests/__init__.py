import sys
from typing import Optional
from unittest import TestCase
# import unittest
#unittest.TestCase.run = lambda self,*args,**kw: unittest.TestCase.debug(self)
from app import db, create_app

from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.users.models.user import User

app = create_app("../tests/config-test.json")
app.app_context().push()

class BaseTestCase(TestCase):
    user:Optional[User] = None
    admin:Optional[User] = None

    @classmethod
    def setUpClass(cls):
        db.session.execute('pragma foreign_keys=on') #type:ignore

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self._app_ctx = self.app.app_context()  # Create a new application context
        self._app_ctx.push()  # Push the application context
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.maxDiff = None


    def tearDown(self):
        db.drop_all()
        self._ctx.pop()  # Pop the request context
        self._app_ctx.pop() # Pop the application context

    def try_admin_operation(self, operation, 
                            user_name:Optional[str]=None, user_password='1',
                            admin_name:Optional[str]=None, admin_password='1', admin_only=False):
        '''
        Attempt an admin operation
        @param operation: function - a function to execute
        @param user_name: str - user name to authenticate as
        @param user_password: str - user password to authenticate
        @param admin_name: str - admin name to authenticate as
        @param admin_password: str - admin password to authenticate
        @param admin_only: bool - if `true` - do not try to perform operation as a user
        '''
        if user_name is None and self.user:
            user_name = self.user.username
        if admin_name is None and self.admin:
            admin_name = self.admin.username
        res = operation()
        self.assertEqual(res.status_code, 302)
        if not admin_only:
            res = self.login(user_name, user_password)
            res = operation()
            self.assertEqual(res.status_code, 302)
            self.logout()
        self.login(admin_name, admin_password)
        return operation()

    def try_user_operation(self, operation, user_name=None, user_password='1'):
        if user_name is None and self.user:
            user_name = self.user.username
        res = operation()
        self.assertEqual(res.status_code, 302)
        res = self.login(user_name, user_password)
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
            db.session.add(entity) #type:ignore
            db.session.commit() #type:ignore
        except Exception as e:
            print(f'Exception while trying to add <{entity}>:', e)
            db.session.rollback() #type:ignore

    def try_add_entities(self, entities):
        for entity in entities:
            self.try_add_entity(entity)
