#!bin/python3

'''Sets default settings to DB if they aren't there'''
from datetime import datetime
from app import create_app, db
from app.settings.models.setting import Setting

create_app().app_context().push()

settings = [
    {'key': 'check_outsiders', 'value': False, 'description': 'Define whether to check network outsiders'},
    {'key': 'crisp.id', 'value': None, 'description': 'Crisp chat ID. If is set to None the Crisp chat is disabled' },
    {'key': 'jivochat.id', 'value': None, 'description': 'Jivochat ID. If is set to None the Jivochat is disabled' },
    {'key': 'network.root_id', 'value': None, 'description': 'ID of the tree\'s root node'}
]

for setting in settings:
    if not Setting.query.get(setting['key']):
        db.session.add(Setting(
            key=setting['key'],
            value=setting['value'],
            default_value=setting['value'],
            description=setting['description'],
            when_created=datetime.now()
        ))
db.session.commit()
