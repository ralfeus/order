"""
Tests verifying correct SQLAlchemy 2.0 migration.

Covers the specific patterns that changed during the migration:
  - db.session.get() (replaces Query.get())
  - text() for raw SQL execution
  - attribute_keyed_dict collections (replaces attribute_mapped_collection)
  - lazy='select' relationships (replaces lazy='dynamic')
"""
from sqlalchemy import select, text

from tests import BaseTestCase, db
from app.currencies.models.currency import Currency
from app.models.country import Country
from app.orders.models.order import Order, OrderParam
from app.orders.models.order_status import OrderStatus
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.payments.models.payment import Payment, PaymentStatus
from app.products.models.product import Product
from app.shipping.models.shipping import NoShipping
from app.users.models.role import Role
from app.users.models.user import User


def _make_admin():
    role = Role(name='admin')
    user = User(
        username='migration_admin',
        email='migration_admin@test.com',
        password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
        enabled=True,
        roles=[role],
    )
    return role, user


def _make_user():
    user = User(
        username='migration_user',
        email='migration_user@test.com',
        password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
        enabled=True,
    )
    return user


class TestSessionGetIntPk(BaseTestCase):
    """db.session.get() works for integer primary keys."""

    def setUp(self):
        super().setUp()
        db.create_all()
        role, admin = _make_admin()
        user = _make_user()
        self.try_add_entities([role, admin, user])
        self.user_id = user.id

    def test_session_get_returns_correct_object(self):
        result = db.session.get(User, self.user_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.username, 'migration_user')

    def test_session_get_returns_none_for_missing_pk(self):
        result = db.session.get(User, 99999)
        self.assertIsNone(result)


class TestSessionGetStringPk(BaseTestCase):
    """db.session.get() works for string primary keys (e.g. Currency)."""

    def setUp(self):
        super().setUp()
        db.create_all()
        self.try_add_entities([
            Currency(code='USD', name='US Dollar', rate=1.0, enabled=True),
        ])

    def test_session_get_string_pk_returns_correct_object(self):
        result = db.session.get(Currency, 'USD')
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'US Dollar')

    def test_session_get_string_pk_returns_none_for_missing(self):
        result = db.session.get(Currency, 'ZZZ')
        self.assertIsNone(result)


class TestTextSqlExecution(BaseTestCase):
    """db.session.execute(text(...)) works correctly."""

    def setUp(self):
        super().setUp()
        db.create_all()
        self.try_add_entities([
            Currency(code='KRW', name='Korean Won', rate=1.0, enabled=True, base=True),
        ])

    def test_text_select(self):
        result = db.session.execute(
            text("SELECT code FROM currencies WHERE code = :code"),
            {'code': 'KRW'}
        ).fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'KRW')

    def test_text_pragma(self):
        """PRAGMA execution via text() must not raise."""
        db.session.execute(text('pragma foreign_keys=on'))


class TestAttributeKeyedDictCollection(BaseTestCase):
    """attribute_keyed_dict collections work after renaming from attribute_mapped_collection."""

    def setUp(self):
        super().setUp()
        db.create_all()
        role, admin = _make_admin()
        user = _make_user()
        country = Country(id='kr', name='Korea', sort_order=0)
        currency = Currency(code='KRW', name='Korean Won', rate=1.0, enabled=True, base=True)
        shipping = NoShipping()
        self.try_add_entities([role, admin, user, country, currency, shipping])
        self.order = Order(
            user=user,
            customer_name='Test Customer',
            address='Test Address',
            country=country,
            phone='010-0000-0000',
            shipping=shipping,
        )
        self.try_add_entity(self.order)

    def test_order_params_keyed_dict_set_and_get(self):
        """OrderParam keyed-dict collection supports dict-style access."""
        param = OrderParam(order=self.order, name='test_key', value='test_value')
        db.session.add(param)
        db.session.commit()

        # Re-fetch to ensure it comes from the DB
        order = db.session.get(Order, self.order.id)
        self.assertIn('test_key', order.order_params)
        self.assertEqual(order.order_params['test_key'].value, 'test_value')

    def test_order_params_multiple_keys(self):
        """Multiple params stored and retrieved via keyed-dict collection."""
        for key, val in [('k1', 'v1'), ('k2', 'v2'), ('k3', 'v3')]:
            db.session.add(OrderParam(order=self.order, name=key, value=val))
        db.session.commit()

        order = db.session.get(Order, self.order.id)
        self.assertEqual(len(order.order_params), 3)
        self.assertEqual(order.order_params['k2'].value, 'v2')


class TestLazySelectRelationships(BaseTestCase):
    """Formerly lazy='dynamic' relationships return lists and are filterable."""

    def setUp(self):
        super().setUp()
        db.create_all()
        role, admin = _make_admin()
        user = _make_user()
        country = Country(id='kr', name='Korea', sort_order=0)
        currency = Currency(code='KRW', name='Korean Won', rate=1.0, enabled=True, base=True)
        shipping = NoShipping()
        self.try_add_entities([role, admin, user, country, currency, shipping])
        self.user = user
        self.country = country
        self.shipping = shipping

    def _make_order(self, username_suffix='a'):
        sub = Subcustomer(username=f'sub_{username_suffix}', name=f'Sub {username_suffix}')
        self.try_add_entity(sub)
        order = Order(
            user=self.user,
            customer_name='Test',
            address='Addr',
            country=self.country,
            phone='010-0000-0000',
            shipping=self.shipping,
        )
        self.try_add_entity(order)
        suborder = Suborder(order=order, subcustomer=sub)
        self.try_add_entity(suborder)
        return order, suborder

    def test_suborders_relationship_is_list(self):
        """Order.suborders is a plain list, not a Query object."""
        order, _ = self._make_order()
        result = db.session.get(Order, order.id)
        self.assertIsInstance(result.suborders, list)

    def test_suborders_len_count(self):
        """len() works on formerly-dynamic suborders relationship."""
        order, _ = self._make_order()
        result = db.session.get(Order, order.id)
        self.assertEqual(len(result.suborders), 1)

    def test_suborders_select_filter(self):
        """Explicit select() query on suborders works correctly."""
        order, suborder = self._make_order()
        sub_id = suborder.subcustomer_id

        rows = db.session.execute(
            select(Suborder).where(
                Suborder.order_id == order.id,
                Suborder.subcustomer_id == sub_id,
            )
        ).scalars().all()
        self.assertEqual(len(rows), 1)

    def test_payment_orders_relationship_is_list(self):
        """Payment.orders is a plain list after lazy='select' migration."""
        payment = Payment(
            user=self.user,
            currency_code='KRW',
            amount_sent_original=1000,
        )
        self.try_add_entity(payment)
        result = db.session.get(Payment, payment.id)
        self.assertIsInstance(result.orders, list)
