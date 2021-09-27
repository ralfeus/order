'''Root module management'''
from importlib import import_module
import os, os.path

def init(app):
    '''Initializes all modules'''
    modules_dir = os.path.dirname(__file__)
    files = os.listdir(modules_dir)
    for file in files:
        if file.startswith('__'):
            continue
        module = import_module(__name__ + '.' + os.path.splitext(file)[0])
        module.init(app)
