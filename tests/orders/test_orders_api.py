'''
Tests of sale order functionality API
'''
from app.shipping.models.shipping import NoShipping
from datetime import datetime

from unittest.mock import patch
from tests import BaseTestCase, db
from app.models import Country
from app.addresses.models import Address
from app.currencies.models import Currency
from app.orders.models.order import Order
from app.orders.models.order_status import OrderStatus
from app.orders.models.order_product import OrderProduct, OrderProductStatus, \
    OrderProductStatusEntry
from app.orders.models.subcustomer import Subcustomer
from app.orders.models.suborder import Suborder
from app.products.models import Product
from app.purchase.models import Company, PurchaseOrder
from app.settings.models import Setting
from app.shipping.models import PostponeShipping, Shipping, ShippingRate
from app.users.models.role import Role
from app.users.models.user import User

class TestOrdersApi(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(name='admin')
        self.user = User(username='user1_test_orders_api', email='root_test_orders_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
            enabled=True, roles=[Role(name='allow_create_po')])
        self.admin = User(username='root_test_orders_api', email='root_test_orders_api@name.com',
            password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
            enabled=True, roles=[admin_role])
        self.try_add_entities([
            self.user, self.admin, admin_role,
            Currency(code='USD', rate=0.5),
            Currency(code='RUR', rate=0.5),
            Currency(code='CZK', rate=1),
            Country(id='c1', name='country1'),
            Product(id='0000', name='Test product', price=10, weight=10),
            Shipping(id=1, name='Shipping1'),
            ShippingRate(shipping_method_id=1, destination='c1', weight=1000, rate=100),
            ShippingRate(shipping_method_id=1, destination='c1', weight=10000, rate=200),
            NoShipping(id=999)
        ])

    def test_create_order(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(order.total_krw, 2620)
        self.assertEqual(order.shipping.name, 'Shipping1')

    def test_create_weightless_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([Product(id=gen_id, name='0', price=10, weight=0)])
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending)
        suborder = Suborder(order=order)
        self.try_add_entities([
            Order(user=self.user),
            order, suborder,
            OrderProduct(suborder=suborder, product_id=gen_id, quantity=1),
        ])
        suborder.get_total()
        

    def test_create_order_over_10_products(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10),
            Product(id='0002', name='Product 2', price=10, weight=10),
            Product(id='0003', name='Product 3', price=10, weight=10),
            Product(id='0004', name='Product 4', price=10, weight=10),
            Product(id='0005', name='Product 5', price=10, weight=10),
            Product(id='0006', name='Product 6', price=10, weight=10),
            Product(id='0007', name='Product 7', price=10, weight=10),
            Product(id='0008', name='Product 8', price=10, weight=10),
            Product(id='0009', name='Product 9', price=10, weight=10),
            Product(id='0010', name='Product 10', price=10, weight=10),
            Product(id='0011', name='Product 11', price=10, weight=10),
            Product(id='0012', name='Product 12', price=10, weight=10),
            Product(id='0013', name='Product 13', price=10, weight=10),
            Product(id='0014', name='Product 14', price=10, weight=10),
            Product(id='0015', name='Product 15', price=10, weight=10),
            Product(id='0016', name='Product 16', price=10, weight=10),
            Product(id='0017', name='Product 17', price=10, weight=10),
            Product(id='0018', name='Product 18', price=10, weight=10),
            Product(id='0019', name='Product 19', price=10, weight=10),
            Product(id='0020', name='Product 20', price=10, weight=10)
        ])        
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"},
                            {"item_code":"2", "quantity": "1"},
                            {"item_code":"3", "quantity": "1"},
                            {"item_code":"4", "quantity": "1"},
                            {"item_code":"5", "quantity": "1"},
                            {"item_code":"6", "quantity": "1"},
                            {"item_code":"7", "quantity": "1"},
                            {"item_code":"8", "quantity": "1"},
                            {"item_code":"9", "quantity": "1"},
                            {"item_code":"10", "quantity": "1"},
                            {"item_code":"11", "quantity": "1"},
                            {"item_code":"12", "quantity": "1"},
                            {"item_code":"13", "quantity": "1"},
                            {"item_code":"14", "quantity": "1"},
                            {"item_code":"15", "quantity": "1"},
                            {"item_code":"16", "quantity": "1"},
                            {"item_code":"17", "quantity": "1"},
                            {"item_code":"18", "quantity": "1"},
                            {"item_code":"19", "quantity": "1"},
                            {"item_code":"20", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(len(order.order_products), 21)
        self.assertEqual(order.suborders.count(), 3)

    def test_create_order_overweight(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=1000)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "11"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 409)
    
    def test_create_order_wrong_input(self):
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={

            })
        )
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1"
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1"
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1"
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '0000'
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '0000',
            "shipping":"1"
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '0000',
            "shipping":"1",
            "phone":"1"
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '00001111222233334444',
            "shipping":"1",
            "phone":"1",
            'comment': None,
            "suborders": [
                {
                    "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                    "items": [
                        {"item_code":"0000", "quantity":"1"},
                        {"item_code":"1", "quantity": "11"}
                    ]
                }
            ]
        })
        self.assertEqual(res.status_code, 409)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '0000',
            "shipping":"1",
            "phone":"1",
            'comment': None,
            "suborders": [
                {
                    "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                    "items": [
                        {"item_code":"0000", "quantity":"1"},
                        {"item_code":"1", "quantity": "11"}
                    ]
                }
            ]
        })
        self.assertEqual(res.status_code, 200)

    def test_create_order_double_product(self):
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity": "1"},
                            {"item_code":"0000", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(order.suborders[0].order_products.count(), 1)
        self.assertEqual(order.suborders[0].order_products[0].quantity, 2)

    def test_handle_wrong_subcustomer_data(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, "  + "P@ssw0rd" * 5,
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, "  + "P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    },
                    {
                        "subcustomer":"A001, Subcustomer2, "  + "P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": ""}
                        ]
                    }
                ]
        })
        self.assertEqual(res.status_code, 409)


    def test_update_subcustomer_password(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '00000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Subcustomer.query.filter_by(username='A000').count(), 1)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '0000',
            "shipping":"1",
            "phone":"1",
            "comment":"",
            "suborders": [
                {
                    "subcustomer":"A000, Subcustomer1, 111",
                    "items": [
                        {"item_code":"0000", "quantity":"1"},
                        {"item_code":"1", "quantity": "1"}
                    ]
                }
            ]
        })
        self.assertEqual(res.status_code, 200)
        subcustomer = Subcustomer.query.filter_by(username='A000')
        self.assertEqual(subcustomer.count(), 1)
        self.assertEqual(subcustomer.first().password, '111')

    def test_delete_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user, status=OrderStatus.pending)
        order.params['p1'] = 'P1' # type: ignore
        order1 = Order(id=gen_id + '1', user=self.user, status=OrderStatus.shipped)
        order2 = Order(id=gen_id + '2', user=self.user)
        suborder = Suborder(order=order)
        self.try_add_entities([
            Order(user=self.user),
            order, order1, order2, suborder,
            OrderProduct(suborder=suborder, product_id='0000'),
            OrderProduct(suborder=suborder, product_id='0000')
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f'/api/v1/admin/order/{gen_id}')
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Order.query.count(), 3)
        res = self.client.delete(f'/api/v1/admin/order/{order1.id}')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(Order.query.count(), 3)
        res = self.client.delete(f'/api/v1/admin/order/{order2.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Order.query.count(), 2)
        
    def test_save_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id, user=self.user)
        ])
        res = self.try_admin_operation(admin_only=True,
            operation=lambda: self.client.post(f'/api/v1/order/{gen_id}', json={
                'address': 'Address1',
                'country': 'c1',
                'customer_name': "Customer1",
                'phone': '1',
                'zip': '1',
                'shipping': '1',
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"100"}
                        ]
                    }
                ]
            }))
        self.assertEqual(res.status_code, 200)

    def test_save_order_add_suborder(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id, user=self.user)
        ])
        res = self.try_admin_operation(admin_only=True,
            operation=lambda: self.client.post(f'/api/v1/order/{gen_id}', json={
                'address': 'Address1',
                'country': 'c1',
                'customer_name': "Customer1",
                'phone': '1',
                'zip': '1',
                'shipping': '1',
                'suborders': [
                    {
                        'subcustomer': 'test, test, test',
                        'items': [
                            {
                                'item_code': '0000',
                                'quantity': 1
                            }
                        ]
                    }
                ]
            }))
        self.assertEqual(res.status_code, 200)

    def test_create_order_from_draft(self):
        order = Order(user=self.user, status=OrderStatus.draft)
        order.params['p1'] = 'P1' # type: ignore
        subcustomer = Subcustomer(name='A000', username='A000')
        suborder = Suborder(order=order, subcustomer=subcustomer)
        self.try_add_entities([
            order, suborder, subcustomer,
            OrderProduct(suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        self.try_user_operation(
            operation=lambda: self.client.post(f'/api/v1/order/{order.id}', json={
                'address': 'Address1',
                'country': 'c1',
                'customer_name': "Customer1",
                'phone': '1',
                'zip': '1',
                'shipping': '999',
                'suborders': [
                    {
                        'subcustomer': 'A000',
                        'seq_num': 1,
                        'items': [
                            {
                                'item_code': '0000',
                                'quantity': 3000
                            }
                        ]
                    }
                ],
                'params': {
                    'p1': 'P1'
                }
            }))
        o = Order.query.first()
        self.assertEqual(o.address, 'Address1')
        
    def test_increase_order_amount_over_free_shipping_threshold(self):
        order = Order(user=self.user)
        subcustomer = Subcustomer(name='A000', username='A000')
        suborder = Suborder(order=order, subcustomer=subcustomer)
        self.try_add_entities([
            order, suborder, subcustomer,
            OrderProduct(suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        res = self.try_admin_operation(admin_only=True,
            operation=lambda: self.client.post(f'/api/v1/order/{order.id}', json={
                'address': 'Address1',
                'country': 'c1',
                'customer_name': "Customer1",
                'phone': '1',
                'zip': '1',
                'shipping': '999',
                'suborders': [
                    {
                        'subcustomer': 'A000',
                        'seq_num': 1,
                        'items': [
                            {
                                'item_code': '0000',
                                'quantity': 3000
                            }
                        ]
                    }
                ]
            }))
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(order.id)
        self.assertEqual(order.total_krw, 30000)

    def test_get_orders(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user, country_id='c1', shipping_method_id=1)
        suborder = Suborder(order=order)
        self.try_add_entities([
            order, suborder,
            OrderProduct(id=10, suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/order'))
        self.assertEqual(res.json[0]['total'], 2700)

    def test_get_order(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order = Order(id=gen_id, user=self.user)
        suborder = Suborder(order=order)
        self.try_add_entities([
            Product(id=gen_id, price=10, weight=10)
        ])
        self.try_add_entities([
            order, suborder,
            OrderProduct(suborder=suborder, product_id=gen_id, price=10, quantity=10),
            Order(id=gen_id+'1', user=self.user, status=OrderStatus.pending)
        ])
        res = self.try_user_operation(
            lambda: self.client.get(f'/api/v1/order/{gen_id}'))
        self.assertEqual(res.json['total'], 2600)
        self.assertEqual(res.json['total_rur'], 1300.0)
        self.assertEqual(res.json['total_usd'], 1300.0)
        self.assertEqual(res.json['user'], self.user.username)
        self.assertEqual(len(res.json['order_products']), 1)
        res = self.client.get('/api/v1/order')
        self.assertEqual(len(res.json), 2)
        res = self.client.get('/api/v1/order?status=pending')
        self.assertEqual(res.json[0]['status'], 'pending')

    def test_get_order_products(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        subcustomer = Subcustomer()
        order = Order(id=gen_id, user_id=self.user.id, status=OrderStatus.pending, country_id='c1',
                  shipping_method_id=1,
                  tracking_id='T00', tracking_url='https://tracking.fake/T00')
        suborder = Suborder(order=order, subcustomer=subcustomer)
        self.try_add_entities([
            order,
            subcustomer,
            suborder
        ])
        
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/admin/order/product'))

    def test_save_order_product(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        op_id = datetime.now().microsecond
        order = Order(id=gen_id, user=self.user)
        suborder = Suborder(id=op_id, order=order)
        self.try_add_entities([
            order, suborder,
            OrderProduct(id=op_id, suborder_id=op_id, product_id='0000', price=10,
                quantity=10, status='pending')
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/product/{op_id}', json={
            'quantity': 100
        }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['quantity'], 100)

        res = self.client.get(f'/api/v1/admin/order/{gen_id}')
        self.assertTrue(res.json['total_krw'], 1010)

    def test_get_order_product_status_history(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        subcustomer = Subcustomer()
        order = Order(id=gen_id, user_id=self.user.id, status='pending', country_id='c1',
                  tracking_id='T00', tracking_url='https://tracking.fake/T00')
        suborder = Suborder(order=order, subcustomer=subcustomer)
        self.try_add_entities([
            order, subcustomer, suborder,
            OrderProduct(id=10, suborder=suborder, product_id='0000', price=10, 
                quantity=10),
            OrderProductStatusEntry(order_product_id=10, user_id=self.admin.id,
                when_created=datetime(2020, 1, 1, 1, 0, 0),
                status=OrderProductStatus.pending)
        ])
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/order/product/10/status/history'))
        res = self.client.get('/api/v1/order/product/10/status/history')
        self.assertEqual(res.json, [{
            'when_created': '2020-01-01 01:00:00',
            'set_by': 'root_test_orders_api',
            'status': 'pending'
        }])
        res = self.client.get('/api/v1/order/product/30/status/history')
        self.assertEqual(res.status_code, 404)

    def test_validate_subcustomer(self):
        setting = Setting(key='order.new.check_subcustomers', value=1, default_value=1)
        self.try_add_entities([
            setting
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order/subcustomer/validate', json={
                'subcustomer': 'test, test, test'
            }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['result'], 'failure')
        res = self.client.post('/api/v1/order/subcustomer/validate', json={
                'subcustomer': '23426444, Mike, atomy#01'
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['result'], 'success')
        
        # Test subcustomer isn't to be checked
        setting.value = False
        res = self.client.post('/api/v1/order/subcustomer/validate', json={
            'subcustomer': 'test, test, test'
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json['result'], 'success')

    def test_parse_subcustomer(self):
        from app.orders.routes.api import parse_subcustomer
        result = parse_subcustomer('test,test,test')
        self.assertEqual(result[0].password, 'test')
        result = parse_subcustomer('test,test,test,')
        self.assertEqual(result[0].password, 'test,')

    def test_get_orders_to_attach(self):
        postpone_shipping = PostponeShipping()
        self.try_add_entities([
            postpone_shipping,
            Order(shipping=postpone_shipping, user=self.user, status=OrderStatus.pending)
        ])
        res = self.try_user_operation(
            lambda: self.client.get('/api/v1/order?to_attach')
        )
        self.assertEqual(len(res.json), 1)

    def test_postponed_orders(self):
        postpone_shipping = PostponeShipping()
        postponed_order = Order(
            shipping=postpone_shipping, user=self.user, status=OrderStatus.pending)
        suborder = Suborder(order=postponed_order)
        self.try_add_entities([
            postpone_shipping, postponed_order, suborder,
            OrderProduct(suborder=suborder, product_id='0000', price=10, quantity=10)
        ])
        postponed_order1 = Order(
            shipping=postpone_shipping, user=self.user, status=OrderStatus.pending)
        suborder1 = Suborder(order=postponed_order1)
        self.try_add_entities([
            postponed_order1, suborder1,
            OrderProduct(suborder=suborder1, product_id='0000', price=10, quantity=10)
        ])
        postponed_order.update_total()
        postponed_order1.update_total()
        res = self.try_admin_operation(admin_only=True,
            operation=lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"100"}
                        ]
                    }
                ],
                "attached_orders": [postponed_order.id]
            })
        )
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(res.json['order_id'])
        self.assertEqual(order.attached_orders.count(), 1)
        self.assertEqual(order.shipping_krw, 200)
        self.assertEqual(order.total_krw, 3700)
        self.client.post(f'/api/v1/order/{order.id}', json={
            'address': 'Address1',
            'country': 'c1',
            'customer_name': "User1",
            'phone': '1',
            'zip': '0000',
            'shipping': '1',
            "attached_orders": [postponed_order.id, postponed_order1.id],
            "suborders": [
                {
                    "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                    "items": [
                        {"item_code":"0000", "quantity":"100"}
                    ]
                }
            ]
        })
        self.assertEqual(order.attached_orders.count(), 2)
        self.assertEqual(order.shipping_krw, 200)
        self.assertEqual(order.total_krw, 3700)

    def test_pay_order(self):
        self.user.balance = 2600
        order = Order(
            user=self.user, status=OrderStatus.pending)
        suborder = Suborder(order=order)
        self.try_add_entities([
            order, suborder,
            OrderProduct(suborder=suborder, product_id='0000', price=10,
                quantity=10, status='purchased')
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/{order.id}', json={
                'status': 'shipped'
            })
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.user.balance, 0)

    def test_create_empty_order(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    },
                    {
                        'subcustomer': 'A001, Subcustomer1, P@ssw0rd',
                        "items": [
                            {'item_code': '', 'quantity': 1}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(order.suborders.count(), 1)
        res = self.client.post('/api/v1/order', json={
            "customer_name":"User1",
            "address":"Address1",
            "country":"c1",
            'zip': '0000',
            "shipping":"1",
            "phone":"",
            "comment":"",
            "suborders": [
                {
                    'subcustomer': 'A001, Subcustomer1, P@ssw0rd',
                    "items": [
                            {'item_code': '', 'quantity': 1}
                        ]
                }
            ]
        })
        self.assertEqual(res.status_code, 409)

    def test_finish_order_with_unfinished_products(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10),
            Product(id='0002', name='Product 2', price=10, weight=10),
            Product(id='0003', name='Product 3', price=10, weight=10),
            Order(id=gen_id)
        ])
        self.try_add_entities([
            Suborder(id=gen_id, order_id=gen_id),
            OrderProduct(suborder_id=gen_id, product_id='0001', quantity=1,
                status=OrderProductStatus.pending),
            OrderProduct(suborder_id=gen_id, product_id='0002', quantity=1,
                status=OrderProductStatus.pending),
            OrderProduct(suborder_id=gen_id, product_id='0003', quantity=1,
                status=OrderProductStatus.pending)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/{gen_id}', json={
                 'status':  'shipped'
        }))
        self.assertEqual(res.status_code, 409)

    def test_finish_order_with_unavailable_products(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10, points=10),
            Product(id='0002', name='Product 2', price=10, weight=10, points=10),
            Product(id='0003', name='Product 3', price=10, weight=10, points=10),
            Order(id=gen_id, country_id='c1', shipping_method_id=1, user=self.user)
        ])
        self.try_add_entities([
            Suborder(id=gen_id, order_id=gen_id),
            OrderProduct(suborder_id=gen_id, product_id='0001', quantity=1,
                status=OrderProductStatus.purchased),
            OrderProduct(suborder_id=gen_id, product_id='0002', quantity=1,
                status=OrderProductStatus.purchased),
            OrderProduct(suborder_id=gen_id, product_id='0003', quantity=1,
                status=OrderProductStatus.unavailable)
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/{gen_id}', json={
                 'status':  'shipped'
        }))
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(gen_id)
        self.assertEqual(order.total_krw, 2620)
        self.assertEqual(order.get_total_points(), 20)

    def test_delete_last_order_item_in_suborder(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10, points=10),
            Order(id=gen_id, country_id='c1', shipping_method_id=1, user=self.user)
        ])
        self.try_add_entities([
            Suborder(id=gen_id, order_id=gen_id),
            OrderProduct(suborder_id=gen_id, product_id='0001', quantity=1,
                status=OrderProductStatus.pending),
            Suborder(id=gen_id + "2", order_id=gen_id),
            OrderProduct(suborder_id=gen_id + "2", product_id='0001', quantity=1,
                status=OrderProductStatus.pending)
        ])

        res = self.try_admin_operation(admin_only=True,
            operation=lambda: self.client.post(f'/api/v1/order/{gen_id}', json={
                "suborders": [
                    {
                        'subcustomer': 'A001, Subcustomer1, P@ssw0rd',
                        "items": [
                                {'item_code': '0001', 'quantity': 1}
                            ]
                    }
                ]
            })
        )
        self.assertEqual(res.status_code, 200)
        order = Order.query.get(gen_id)
        self.assertEqual(order.suborders.count(), 1)

    def test_delete_order_draft(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        order1 = Order(id=gen_id, country_id='c1', shipping_method_id=1, user=self.user,
                status=OrderStatus.pending)
        order2 = Order(id=gen_id + "2", country_id='c1', shipping_method_id=1, user=self.user,
                status=OrderStatus.pending)
        order3 = Order(id=gen_id + "3", country_id='c1', shipping_method_id=1, user=self.user,
                status=OrderStatus.pending)
        self.try_add_entities([
            order1, order2, order3,
            Suborder(id=order1.id, order_id=order1.id),
            OrderProduct(suborder_id=order1.id, product_id='0000', quantity=1,
                status=OrderProductStatus.pending),
            Suborder(id=order2.id, order_id=order2.id),
            OrderProduct(suborder_id=order2.id, product_id='0000', quantity=1,
                status=OrderProductStatus.pending),
            Suborder(id=order3.id, order_id=order3.id),
            OrderProduct(suborder_id=order3.id, product_id='0000', quantity=1,
                status=OrderProductStatus.pending)
        ])

        # First try to delete non-draft order. Should return 404
        res = self.try_user_operation(
            operation=lambda: self.client.delete(f'/api/v1/order/{order2.id}')
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(Order.query.count(), 3)

        # Now deleting draft
        order2.status = OrderStatus.draft
        order3.status = OrderStatus.draft
        db.session.commit()
        res = self.client.delete(f'/api/v1/order/{order3.id}')
        self.assertEqual(res.status_code, 200)
        orders = Order.query.all()
        self.assertEqual(orders, [order1, order2])
        # self.assertEqual(Order.query.last(), order3)

    def test_order_status(self):
        order = Order(status=OrderStatus.ready_to_ship)
        db.session.add(order)
        db.session.flush()

    def test_set_status_shipped_twice(self):
        gen_id = f'{__name__}-{int(datetime.now().timestamp())}'
        self.try_add_entities([
            Order(id=gen_id, user=self.user, status=OrderStatus.pending, country_id='c1', total_krw=1000)        
        ])
        self.user.balance = 1000
        db.session.commit()
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/order/{gen_id}', json={
                "status": "shipped"
        }))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.user.balance, 0)
        self.client.post(f'/api/v1/admin/order/{gen_id}', json={
                "status": "shipped"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.user.balance, 0)


    def test_create_11th_order_draft(self):
        self.try_add_entities([
            Order(id=f'ORD-drft-{self.user.id}-9', seq_num=9),
            Order(id=f'ORD-drft-{self.user.id}-10', seq_num=10),
            Product(id='0001', name='Product 1', price=10, weight=10)
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                'draft': True,
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0000", "quantity":"1"},
                            {"item_code":"1", "quantity": "1"}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        created_order_id = res.json['order_id']
        order = Order.query.get(created_order_id)
        self.assertEqual(order.id, f'ORD-drft-{self.user.id}-11')

    def test_create_order_with_po(self):
        self.try_add_entities([
            Product(id='0001', name='Product 1', price=10, weight=10),
            Address(id=1),
            Company(default=True, address_id=1, phone='111')
        ])
        res = self.try_user_operation(
            lambda: self.client.post('/api/v1/order', json={
                "customer_name":"User1",
                "address":"Address1",
                "country":"c1",
                'zip': '0000',
                "shipping":"1",
                "phone":"1",
                "comment":"",
                "create_po": True,
                "suborders": [
                    {
                        "subcustomer":"A000, Subcustomer1, P@ssw0rd",
                        "items": [
                            {"item_code":"0001", "quantity":"1"},
                        ]
                    },
                    {
                        'subcustomer': 'A001, Subcustomer1, P@ssw0rd',
                        "items": [
                            {'item_code': '0001', 'quantity': 1}
                        ]
                    }
                ]
        }))
        self.assertEqual(res.status_code, 200)
        order_id = res.json['order_id']
        purchase_orders = PurchaseOrder.query.filter(PurchaseOrder.id.like(f'PO-{order_id[4:]}%'))
        self.assertEqual(purchase_orders.count(), 2)
