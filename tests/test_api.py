import unittest
from app import create_app, db
from app.config import TestConfig
import app.routes.api as test_target

app = create_app(TestConfig)
app.app_context().push()
# Common test initialization
from app.models import Currency
db.create_all()

class TestClientApi(unittest.TestCase):
    def setUp(self):
        currencies = [
            Currency(code='USD', name='US Dollar', rate=1),
            Currency(code='RUR', name='Russian rouble', rate=1)
        ]
        db.session.add_all(currencies)
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

if __name__ == '__main__':
    unittest.main()
