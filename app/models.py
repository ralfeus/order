'''
Contains models (entities) of the application
'''
from flask_login import UserMixin
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login

@login.user_loader
def load_user(id):
    return User(id=id)


class Currency(db.Model):
    __tablename__ = 'currencies'

    code = Column(String(3), primary_key=True)
    name = Column(String(64))
    rate = Column(Float(5))

    def __repr__(self):
        return "<Currency: {}>".format(self.code)


class Order(db.Model):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    name = Column(String(16))
    address = Column(String(64))
    country = Column(String(128))
    phone = Column(String(32))
    comment = Column(String(128))
    time_created = Column(DateTime)
    order_products = relationship('OrderProduct', backref='order', lazy='dynamic')

    def __repr__(self):
        return "<Order: {}>".format(self.id)

class OrderProduct(db.Model):
    '''
    Represents an ordered item of the order. Doesn't exist apart from order
    '''
    __tablename__ = 'order_products'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(String(16), ForeignKey('products.id'))
    product = relationship('Product')
    quantity = Column(Integer)
    subcustomer = Column(String(256))
    status = Column(String(16))

    def __repr__(self):
        return "<OrderProduct: Order: {}, Product: {}, Status: {}".format(
            self.order_id, self.product_id, self.status)

class Product(db.Model):
    __tablename__ = 'products'

    id = Column(String(16), primary_key=True)
    name = Column(String(256), index=True)
    name_english = Column(String(256), index=True)
    name_russian = Column(String(256), index=True)
    category = Column(String(64))
    weight = Column(Integer)
    price = Column(Integer)
    points = Column(Integer)

    def __repr__(self):
        return "<Product {}:'{}'>".format(self.id, self.name_english)

    @staticmethod
    def get_products(product_query):
        '''
        Returns list of products based on a query
        '''
        return list(map(lambda product: {
            'id': product.id,
            'name': product.name,
            'name_english': product.name_english,
            'name_russian': product.name_russian,
            'price': product.price,
            'weight': product.weight,
            'points': product.points
            }, product_query))

class ShippingRate(db.Model):
    __tablename__ = 'shipping_rates'

    id = Column(Integer, primary_key=True)
    destination = Column(String(32), index=True)
    weight = Column(Integer, index=True)
    rate = Column(Float)

    def __repr__(self):
        return "<{}: {}/{}/{}>".format(type(self), self.destination, self.weight, self.rate)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)
    fname = db.Column(db.String(80))
    lname = db.Column(db.String(80))
    password_hash = db.Column(db.String(200), primary_key=False, unique=False, nullable=False)

    # def __init__(self, id, username, email):
    #     self.id = id
    #     self.username = username
    #     self.email = email

    def get_id(self):
        return User.id

    def set_password(self, password='P@$$w0rd'):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
