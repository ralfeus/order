from datetime import datetime
import unittest
from app import create_app, db
from app.config import TestConfig
import app.routes.api as test_target

app = create_app(TestConfig)
app.app_context().push()
from app.models import Currency, OrderProductStatusEntry, User

class TestClientApi(unittest.TestCase):
    def setUp(self):
        users = [
            User(id=1, username='User1', email='user@name.com', password_hash='#', enabled=True)
        ]
        currencies = [
            Currency(code='USD', name='US Dollar', rate=1),
            Currency(code='RUR', name='Russian rouble', rate=1)
        ]
        order_product_history = [
            OrderProductStatusEntry(order_product_id=1, user_id=1, status="Pending", set_at=datetime(2020, 1, 1, 1, 0, 0)),
            OrderProductStatusEntry(order_product_id=2, user_id=1, status="Pending", set_at=datetime(2020, 1, 1, 1, 0, 0))
        ]
        db.create_all()
        db.session.add_all(currencies)
        db.session.add_all(order_product_history)
        db.session.add_all(users)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_currency_rate(self):
        res = test_target.get_currency_rate()
        self.assertEqual(res.json, {
            'USD': '1.00000',
            'RUR': '1.00000'
        })

    def test_get_order_products_status_history(self):
        res = test_target.get_order_product_status_history(1)
        self.assertEqual(res.json, [{
            'set_at': '2020-01-01 01:00:00',
            'set_by': 'User1',
            'status': 'Pending'
        }])
        res = test_target.get_order_product_status_history(3)
        self.assertEqual(res.status, '404 NOT FOUND')

if __name__ == '__main__':
    unittest.main()
