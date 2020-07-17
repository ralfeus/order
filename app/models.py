from app import db, login
from sqlalchemy import Column, String, Integer, Float

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

@login.user_loader
def load_user(id):
    return User()

class Currency(db.Model):
    __tablename__ = 'currencies'

    code = Column(String(3), primary_key=True)
    name = Column(String(64))
    rate = Column(Float(5))

    def __repr__(self):
        return "<Currency: {}>".format(self.code)

class Order():
    __tablename__ = 'orders'

    id = Column(String(16), primary_key=True)
    product = Column(String(16), index=True)
    name = Column(String(16))
    address = Column(String(64))
    country = Column(String(128))
    phone = Column(Integer)
    comment = Column(String(128))

    def __repr__(self):
        return "<Order: {}>".format(self.id)

class Product(db.Model):
    __tablename__ = 'products'

    id = Column(String(16), primary_key=True)
    name_english = Column(String(256), index=True)
    name_russian = Column(String(256), index=True)
    category = Column(String(64))
    weight = Column(Integer)
    price = Column(Integer)
    points = Column(Integer)

    def __repr__(self):
        return "<Product {}:'{}'>".format(self.id, self.name_english)

class ShippingRate(db.Model):
    __tablename__ = 'shipping_rates'

    id = Column(Integer, primary_key=True)
    destination = Column(String(32), index=True)
    weight = Column(Integer, index=True)
    rate = Column(Float)

    def __repr__(self):
        return "<{}: {}/{}/{}>".format(type(self), self.destination, self.weight, self.rate)

class Order_Product_Status(db.Model):
    __tablename__ = 'order_product_status'

    order_product_status = Column(String(16), primary_key=True)



class User(UserMixin):
    def get_id(self):
        return 0

    def set_password(self, password = 'P@$$w0rd'):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)