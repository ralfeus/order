"""Tests for the `flask eurocargo ship-invoice` command"""
from unittest.mock import MagicMock, patch

from tests import BaseTestCase, db
from app.currencies.models import Currency
from app.invoices.models.invoice import Invoice
from app.models import Country
from app.orders.models.order import Order, OrderBox
from app.orders.models.order_status import OrderStatus
from app.shipping.methods.eurocargo.cli import eurocargo_cli
from app.shipping.models.shipping import NoShipping

URL_PARAM = 'eurocargo.shipment_url'
HANDLERS = 'app.shipping.methods.eurocargo.signal_handlers'


class TestShipInvoiceCommand(BaseTestCase):

    def setUp(self):
        super().setUp()
        db.create_all()
        self.try_add_entities([
            Currency(code='USD', rate=0.5),
            Country(id='DE', name='Germany'),
            NoShipping(id=1),
            Invoice(id='INV-1', currency_code='USD'),
            Invoice(id='INV-EMPTY', currency_code='USD'),
        ])
        self.order1 = self._add_order('ORD-1')
        self.order2 = self._add_order('ORD-2')

    def _add_order(self, order_id, invoice_id='INV-1', boxes=True, **kwargs):
        fields = dict(
            id=order_id, invoice_id=invoice_id, customer_name='Customer',
            email='c@example.com', address='1 Street', city_eng='Berlin',
            country_id='DE', zip='10115', shipping_method_id=1,
            status=OrderStatus.shipped, total_weight=1000,
            shipping_base_currency=5000, total_base_currency=15000)
        fields.update(kwargs)
        order = Order(**fields)
        self.try_add_entity(order)
        if boxes:
            self.try_add_entity(OrderBox(order_id=order_id, length=40, width=30,
                                         height=20, weight=500, quantity=1))
        return order

    def _run(self, *args, response=None):
        runner = self.app.test_cli_runner()
        with patch(f'{HANDLERS}.requests.post') as mock_post, \
             patch(f'{HANDLERS}._eur_rate', return_value=0.001), \
             patch('app.orders.signals.sale_order_shipped.send') as mock_signal:
            if response is None:
                response = MagicMock()
                response.status_code = 201
                response.json.side_effect = lambda: {
                    'token': 't', 'shipment_url': f'http://ec/{mock_post.call_count}'}
            mock_post.return_value = response
            result = runner.invoke(eurocargo_cli, ['ship-invoice', *args])
        return result, mock_post, mock_signal

    def _order(self, order_id) -> Order:
        db.session.expire_all()
        return db.session.get(Order, order_id)  # type: ignore

    def test_invoice_not_found(self):
        result, mock_post, _ = self._run('INV-NONE')
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('INV-NONE not found', result.output)
        mock_post.assert_not_called()

    def test_invoice_without_orders(self):
        result, mock_post, _ = self._run('INV-EMPTY')
        self.assertEqual(result.exit_code, 0)
        self.assertIn('no orders', result.output)
        mock_post.assert_not_called()

    def test_creates_shipment_per_order(self):
        result, mock_post, _ = self._run('INV-1')
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(mock_post.call_count, 2)
        sent_ids = {c[1]['json']['order_id'] for c in mock_post.call_args_list}
        self.assertEqual(sent_ids, {'ORD-1', 'ORD-2'})
        self.assertTrue(self._order('ORD-1').params[URL_PARAM])
        self.assertTrue(self._order('ORD-2').params[URL_PARAM])
        self.assertIn('created: 2, skipped: 0, failed: 0', result.output)

    def test_orders_of_other_invoices_untouched(self):
        self._add_order('ORD-OTHER', invoice_id='INV-EMPTY')
        _, mock_post, _ = self._run('INV-1')
        sent_ids = {c[1]['json']['order_id'] for c in mock_post.call_args_list}
        self.assertNotIn('ORD-OTHER', sent_ids)

    def test_shipping_status_and_totals_unchanged(self):
        self._run('INV-1')
        order = self._order('ORD-1')
        self.assertEqual(order.shipping_method_id, 1)
        self.assertEqual(order.status, OrderStatus.shipped)
        self.assertEqual(order.shipping_base_currency, 5000)
        self.assertEqual(order.total_base_currency, 15000)

    def test_shipped_signal_not_sent(self):
        """Other sale_order_shipped receivers (e.g. warehouse) must not run."""
        _, _, mock_signal = self._run('INV-1')
        mock_signal.assert_not_called()

    def test_skips_order_with_existing_shipment(self):
        self.order1.params[URL_PARAM] = 'http://ec/old'
        db.session.commit()
        result, mock_post, _ = self._run('INV-1')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(self._order('ORD-1').params[URL_PARAM], 'http://ec/old')
        self.assertIn('created: 1, skipped: 1, failed: 0', result.output)

    def test_force_recreates_existing_shipment(self):
        self.order1.params[URL_PARAM] = 'http://ec/old'
        db.session.commit()
        result, mock_post, _ = self._run('INV-1', '--force')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(mock_post.call_count, 2)
        self.assertNotEqual(self._order('ORD-1').params[URL_PARAM], 'http://ec/old')

    def test_dry_run_sends_and_changes_nothing(self):
        result, mock_post, _ = self._run('INV-1', '--dry-run')
        self.assertEqual(result.exit_code, 0)
        mock_post.assert_not_called()
        self.assertNotIn(URL_PARAM, self._order('ORD-1').params)
        self.assertIn('DRY RUN', result.output)

    def test_missing_fields_reported_as_failed(self):
        self._add_order('ORD-NOBOX', boxes=False)
        result, mock_post, _ = self._run('INV-1')
        self.assertEqual(result.exit_code, 1)
        self.assertIn('ORD-NOBOX: FAILED, missing boxes', result.output)
        self.assertEqual(mock_post.call_count, 2)

    def test_eurocargo_error_reported_as_failed(self):
        response = MagicMock()
        response.raise_for_status.side_effect = Exception('500 Server Error')
        result, _, _ = self._run('INV-1', response=response)
        self.assertEqual(result.exit_code, 1)
        self.assertIn('failed: 2', result.output)
        self.assertNotIn(URL_PARAM, self._order('ORD-1').params)
