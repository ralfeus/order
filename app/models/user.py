'''
User model
'''
from flask_login import UserMixin
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash


from app import db

class User(db.Model, UserMixin):
    '''
    Represents site's user
    '''
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)

    email = db.Column(db.String(80))
    password_hash = db.Column(db.String(200))

    orders = relationship('Order', backref='user', lazy='dynamic')
    transactions = relationship('Transaction', backref='user', lazy='dynamic')

    def get_id(self):
        return str(self.id)

    def set_password(self, password='P@$$w0rd'):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
