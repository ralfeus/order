import unittest
from flask_sqlalchemy import SQLAlchemy
from app import app
import app.routes.api as test_target

# Common test initialization
app.config['SQLALCHEMY_DATABASE_URI'] = 'file::memory:'
app.config['TESTING'] = True
db = SQLAlchemy(app)
from app.models import Currency
db.create_all()
db.session.commit()

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
            'USD': 'US Dollar',
            'RUR': 'Russian rouble'
        })

if __name__ == '__main__':
    unittest.main()
