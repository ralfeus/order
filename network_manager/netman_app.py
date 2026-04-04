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

_dir = os.path.dirname(os.path.abspath(__file__))   # network_manager/ (local) or /app/ (Docker)
_root = os.path.dirname(_dir)                         # project root (local) or / (Docker)
sys.path.insert(0, _dir)    # Docker: /app/ has common/ → works
sys.path.insert(0, _root)   # local: project root has common/ → works

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
app.config.from_file(os.path.join(_dir, 'config.json'), load=json.load)
app.config['JSON_AS_ASCII'] = False
app.debug = os.environ.get('LOG_LEVEL', 'INFO') == 'DEBUG'
config.DATABASE_URL = os.environ.get('NEO4J_URL') or app.config['NEO4J_URL']
config.ENCRYPTED = False

if app.debug:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s:%(levelname)s:%(module)s:%(name)s:%(lineno)d:\t%(message)s')
logging.info(f"Logging level: {logging.getLevelName(log_level)}")
import network_manager

logging.info(app.url_map)

__all__ = ['app']
