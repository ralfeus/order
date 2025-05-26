from datetime import datetime
import os

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.settings import bp_api_admin
from app.settings.models.setting import Setting
from app.settings.validators.setting import SettingValidator

@bp_api_admin.route('/', defaults={'setting_id': None}, strict_slashes=False)
@bp_api_admin.route('/<setting_id>')
@login_required
@roles_required('admin')
def get_settings(setting_id):
    '''Returns all or selected settings in JSON'''
    settings = Setting.query.all() \
        if setting_id is None \
        else Setting.query.filter_by(key=setting_id)

    return jsonify(list(map(lambda entry: entry.to_dict(), settings)))

@bp_api_admin.route('/<setting_id>', methods=['POST'])
@login_required
@roles_required('admin')
def save_setting(setting_id):
    '''Creates or modifies existing setting'''
    with SettingValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't update a setting",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            }), 400
    payload = request.get_json()

    setting = Setting.query.get(setting_id)
    if not setting:
        abort(Response(f'No setting <{setting_id}> was found', status=400))

    for key, value in payload.items():
        if getattr(setting, key) != value:
            setattr(setting, key, value)
            setting.when_changed = datetime.now()

    db.session.commit()
    return jsonify({'data': [setting.to_dict()]})

@bp_api_admin.route('/<setting_id>', methods=['DELETE'])
@login_required
@roles_required('admin')
def delete_setting(setting_id):
    '''Deletes existing setting item'''
    setting = Setting.query.get(setting_id)
    if not setting:
        abort(Response(f'No setting <{setting_id}> was found', status=404))
    setting.value = setting.default_value
    db.session.commit()
    return jsonify({'data': [setting.to_dict()]})

@bp_api_admin.route('/restart')
@login_required
@roles_required('admin')
def restart_app():
    ''' Restart whole aplication'''
    os._exit(0)
