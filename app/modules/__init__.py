'''Root module management'''
from importlib import import_module
import os, os.path

from app.settings.models.setting import Setting

def init(app):
    '''Initializes all modules'''
    modules_dir = os.path.dirname(__file__)
    files = os.listdir(modules_dir)
    with app.app_context():
        for file in files:
            if file.startswith('__'):
                continue
            module_name = os.path.splitext(file)[0]
            enabled_setting = Setting.query.get(f'module.{module_name}.enabled')
            if enabled_setting is None or enabled_setting.value == '0':
                continue
            module = import_module(__name__ + '.' + module_name)
            module.init(app)
