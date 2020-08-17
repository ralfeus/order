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
    enabled = Column(db.Boolean(), nullable=False, default=True)

    # User information
    # enabled = Column('is_enabled', db.Boolean(), nullable=False)
    when_created = Column(DateTime, nullable=False)
    when_changed = Column(DateTime)
    # Business
    balance = Column(Integer, default=0)

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
        return list(map(lambda user: user.to_dict(), user_query))
            
    def to_dict(self):
        '''
        Get representation of the transaction as dictionary for JSON conversion
        '''
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'enabled': self.enabled,
            'when_created': self.when_created,
            'when_changed': self.when_changed
        }