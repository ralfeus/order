from tests import BaseTestCase, db
from app.shipping.models import DHL

class TestShippingDHL(BaseTestCase):
    def setUp(self):
        super().setUp()

        db.create_all()
        db.session.execute("INSERT INTO countries VALUES('ua', 'Ukraine', 0)")
        db.session.execute("INSERT INTO dhl_zones VALUES(1)")
        db.session.execute("INSERT INTO dhl_zones VALUES(2)")
        db.session.execute("INSERT INTO dhl_zones VALUES(3)")
        db.session.execute("INSERT INTO dhl_zones VALUES(4)")
        db.session.execute("INSERT INTO dhl_zones VALUES(5)")
        db.session.execute("INSERT INTO dhl_zones VALUES(6)")
        db.session.execute("INSERT INTO dhl_zones VALUES(7)")
        db.session.execute("INSERT INTO dhl_zones VALUES(8)")
        db.session.execute('INSERT INTO dhl_countries VALUES(8, \'ua\')')
        db.session.execute('INSERT INTO dhl_rates VALUES(8, 0.5, 44339)')
        db.session.execute('INSERT INTO dhl_rates VALUES(8, 10, 180919)')
        db.session.execute('INSERT INTO dhl_rates VALUES(8, 99999, 13975)')


    def test_get_rate(self):
        dhl = DHL()
        rate = dhl.get_shipping_cost('ua', 100)
        self.assertEqual(rate, 44339)
        rate = dhl.get_shipping_cost('ua', 100000)
        self.assertEqual(rate, 1397500)
