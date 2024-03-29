'''
User model
'''
import json
from flask_security import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm.attributes import InstrumentedAttribute
from werkzeug.security import check_password_hash, generate_password_hash


from app import db
from app.users.models.role import Role

roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('users.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('roles.id')))

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
    enabled = Column(Boolean, nullable=False, default=False)
    atomy_id = Column(String(10))
    phone = Column(String(32))
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    profile = Column(Text, default='{}')
    fs_uniquifier = Column(String(255), unique=True, nullable=False)
    # User information
    when_created = Column(DateTime)
    when_changed = Column(DateTime)
    # Business
    balance = Column(Integer, default=0)

    def __init__(self, **kwargs):
        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])
        if self.fs_uniquifier is None:
            self.fs_uniquifier = self.username
        # Here properties are set (attributes start with '__')
        if kwargs.get('password') is not None:
            self.set_password(kwargs['password'])
    def get_id(self):
        return str(self.id)

    def get_profile(self) -> dict:
        try:
            return json.loads(self.profile)
        except:
            return {}

    def set_profile(self, value: dict):
        if isinstance(value, dict):
            self.profile = json.dumps(value)

    def set_password(self, password='P@$$w0rd'):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def active(self):
        return self.enabled
    
    @active.setter
    def active(self, value):
        self.enabled = value

    @property
    def password(self):
        raise Exception
    
    @password.setter
    def password(self, value):
        self.set_password(value)

    def __repr__(self):
        return f'<User {self.id}: {self.username}>'

    # @staticmethod
    # def get_user(user_query):
    #     '''
    #     Returns list of users based on a query
    #     '''
    #     return [user.to_dict() for user in user_query]
            
    def to_dict(self):
        '''
        Get representation of the transaction as dictionary for JSON conversion
        '''
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'atomy_id': self.atomy_id,
            'enabled': self.enabled,
            'roles': [role.to_dict() for role in self.roles],
            'balance': self.balance,
            'when_created': self.when_created.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_created else None,
            'when_changed': self.when_changed.strftime('%Y-%m-%d %H:%M:%S') \
                if self.when_changed else None
        }
