'''Root module management'''
from importlib import import_module
import os, os.path

from flask import Flask

from app.settings.models.setting import Setting

def init(app: Flask):
    '''Initializes all modules'''
    logger = app.logger.getChild('modules.init()')
    modules_dir = os.path.dirname(__file__)
    files = os.listdir(modules_dir)
    for file in files:
        if file.startswith('__'):
            continue
        module_name = os.path.splitext(file)[0]
        try:
            if app.config['MODULES'][module_name]['enabled']:
                logger.info("Loading module: %s", module_name)
                module = import_module(__name__ + '.' + module_name)
                module.init(app)
        except KeyError:
            pass
