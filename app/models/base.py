'''
Abscract base model
'''
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app import db

class BaseModel:
    '''
    Base model
    '''
    id = Column(Integer, primary_key=True)
    when_created = Column(DateTime, index=True)
    when_changed = Column(DateTime)

    def __init__(self, **kwargs):
        self.when_created = datetime.now()
        # Set all attributes passed
        attributes = [a[0] for a in type(self).__dict__.items()
                           if isinstance(a[1], InstrumentedAttribute)]
        for arg in kwargs:
            if arg in attributes:
                setattr(self, arg, kwargs[arg])

    @classmethod
    def get_filter(cls, base_filter, column=None, filter_value=None):
        '''Abstract method for returning a filter for a model'''
        raise NotImplementedError(f'get_filter() is not implemented for {cls}')

    def delete(self):
        '''Deletes an entity itself'''
        db.session.delete(self)

    def is_editable(self):
        '''Returns a state of the entity whether it's editable'''
        return True

# from sqlalchemy import exc, event
# from sqlalchemy.pool import Pool

# @event.listens_for(Pool, "checkout")
# def check_connection(dbapi_con, con_record, con_proxy):
#     '''Listener for Pool checkout events that pings every connection before using.
#     Implements pessimistic disconnect handling strategy. See also:
#     http://docs.sqlalchemy.org/en/rel_0_8/core/pooling.html#disconnect-handling-pessimistic'''

#     cursor = dbapi_con.cursor()
#     try:
#         cursor.execute("SELECT 1")  # could also be dbapi_con.ping(),
#                                     # not sure what is better
#     except exc.OperationalError as ex:
#         if ex.args[0] in (2006,   # MySQL server has gone away
#                           2013,   # Lost connection to MySQL server during query
#                           2055):  # Lost connection to MySQL server at '%s', system error: %d
#             # caught by pool, which will retry with a new connection
#             raise exc.DisconnectionError()
#         else:
#             raise
