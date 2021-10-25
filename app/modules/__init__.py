'''Root module management'''
from importlib import import_module
import os, os.path

from app.settings.models.setting import Setting

def init(app):
    '''Initializes all modules'''
    modules_dir = os.path.dirname(__file__)
    files = os.listdir(modules_dir)
    for file in files:
        if file.startswith('__'):
            continue
        module_name = os.path.splitext(file)[0]
        try:
            if app.config['MODULES'][module_name]['enabled']:
                module = import_module(__name__ + '.' + module_name)
                module.init(app)
        except KeyError:
            pass
