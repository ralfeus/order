from . import crisp
from . import jivochat

def init(app):
    crisp.init(app)
    jivochat.init(app)