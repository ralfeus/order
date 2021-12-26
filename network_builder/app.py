# -*- coding: utf-8 -*-
'''Network manager Flask application'''

from json import JSONEncoder
import logging

from flask import Flask
from neomodel import config

################### JSON serialization patch ######################
# In order to have all objects use to_dict() function providing
# dictionary for JSON serialization
def _default(self, obj):
    return getattr(obj.__class__, "to_dict", _default.default)(obj)

_default.default = JSONEncoder.default  # Save unmodified default.
JSONEncoder.default = _default # Replace it.
###################################################################

app = Flask(__name__)
app.config.from_json('config.json')
app.config['JSON_AS_ASCII'] = False
config.DATABASE_URL = app.config['NEO4J_URL']
config.ENCRYPTED_CONNECTION = False

if app.debug:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s:%(levelname)s:%(module)s:%(name)s:%(lineno)d:\t%(message)s')

import network_manager

__all__ = ['app']
