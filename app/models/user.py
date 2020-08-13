'''
User model
'''
from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from werkzeug.security import check_password_hash, generate_password_hash


from app import db

class User(db.Model, UserMixin):
    '''
    Represents site's user
    '''
    __tablename__ = 'users'

    # Identification
    id = Column(Integer, primary_key=True)
    username = Column(String(32), unique=True, nullable=False)
    email = Column(String(80))
    password_hash = Column(String(200))
    enabled = Column(Boolean, nullable=False)

    # Business
    balance = Column(Integer, default=0)

    when_created = Column(DateTime)
    when_changed = Column(DateTime)

    def get_id(self):
        return str(self.id)

    def set_password(self, password='P@$$w0rd'):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get_user(user_query):
        '''
        Returns list of users based on a query
        '''
        return list(map(lambda user: {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'when_created': user.when_created,
            'when_changed': user.when_changed
            }, user_query))
            