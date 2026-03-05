# -*- coding: utf-8 -*-
'''Network manager Flask application'''

import dataclasses
from datetime import date
import decimal
import json
import logging
import os
import sys
import uuid

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
sys.path.insert(0, _dir)                                     # network-manager/ for import network_manager
sys.path.insert(0, os.path.join(_root, 'network-builder'))  # network-builder/ for model imports
sys.path.insert(0, _root)                                    # app root for utils, exceptions

from flask import Flask
from neomodel import config

################### JSON serialization patch ######################
# In order to have all objects use to_dict() function providing
# dictionary for JSON serialization
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return obj.to_dict()
        except:
            if isinstance(obj, date):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(obj, (decimal.Decimal, uuid.UUID)):
                return str(obj)
            if dataclasses and dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj) #type: ignore
            if hasattr(obj, "__html__"):
                return str(obj.__html__())
            return super().default(obj)

###################################################################

app = Flask(__name__)
app.json_encoder = JSONEncoder #type:ignore
app.config.from_file(os.path.join(_root, 'config.json'), load=json.load)
app.config['JSON_AS_ASCII'] = False
config.DATABASE_URL = os.environ.get('NEO4J_URL') or app.config['NEO4J_URL']
config.ENCRYPTED = False

if app.debug:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s:%(levelname)s:%(module)s:%(name)s:%(lineno)d:\t%(message)s')

import network_manager

__all__ = ['app']
