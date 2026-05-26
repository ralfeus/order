'''Tests for post_purchase_orders job — duplicate username scenario'''
from unittest.mock import MagicMock, patch

from app.orders.models.order import Order
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.purchase.models import PurchaseOrder, PurchaseOrderStatus
from app.purchase.jobs import post_purchase_orders

from tests import BaseTestCase, db


def _register_sqlite_lock_functions():
    '''Register GET_LOCK / RELEASE_LOCK as Python functions on the SQLite
    connection so that advisory-lock SQL doesn't raise OperationalError in tests.
    Works because Flask-SQLAlchemy uses StaticPool for sqlite://, meaning the
    session and db.engine.connect() share the same underlying connection.'''
    with db.engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        raw.create_function('GET_LOCK', 2, lambda name, timeout: 1)
        raw.create_function('RELEASE_LOCK', 1, lambda name: 1)


class TestPostPurchaseOrdersDuplicateUsername(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        _register_sqlite_lock_functions()

    @patch('app.purchase.jobs._post_claimed_pos')
    def test_duplicate_username_processes_all_pos(self, mock_post):
        '''When two subcustomers share a username, both their pending POs
        must be processed without raising MultipleResultsFound.'''
        username = 'dupuser01'

        # Create entities sequentially so auto-generated IDs never collide.
        sc1 = Subcustomer(name='Sub One', username=username, password='pass1')
        sc2 = Subcustomer(name='Sub Two', username=username, password='pass2')
        self.try_add_entities([sc1, sc2])

        order1 = Order()
        self.try_add_entity(order1)
        order2 = Order()
        self.try_add_entity(order2)

        sub1 = Suborder(order_id=order1.id, subcustomer_id=sc1.id)
        self.try_add_entity(sub1)
        sub2 = Suborder(order_id=order2.id, subcustomer_id=sc2.id)
        self.try_add_entity(sub2)

        po1 = PurchaseOrder(suborder=sub1, customer_id=sc1.id,
                            status=PurchaseOrderStatus.pending)
        self.try_add_entity(po1)
        po2 = PurchaseOrder(suborder=sub2, customer_id=sc2.id,
                            status=PurchaseOrderStatus.pending)
        self.try_add_entity(po2)

        # side_effect advances PO status to posted so the while-True loop exits.
        def fake_post(claimed_pos, uname, worker_id, logger):
            for po in claimed_pos:
                po.status = PurchaseOrderStatus.posted
            db.session.commit()  # type: ignore

        mock_post.side_effect = fake_post

        post_purchase_orders.apply()

        # _post_claimed_pos must have been called once per subcustomer
        self.assertEqual(mock_post.call_count, 2)
