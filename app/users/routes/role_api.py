from flask import jsonify, request
from flask_security import roles_required

from app.users import bp_api_admin
from app.users.models.role import Role

@bp_api_admin.route('/role')
@roles_required('admin')
def get_role():
    '''Returns list of roles'''
    roles = Role.query

    if request.values.get('initialValue') is not None:
        role = roles.get(request.values.get('value'))
        return jsonify(
            {'id': role.id, 'text': role.name} \
                if role is not None else {})
    if request.values.get('q') is not None:
        roles = roles.filter(Role.name.like(f'%{request.values["q"]}%'))
    if request.values.get('page') is not None:
        page = int(request.values['page'])
        total_results = roles.count()
        roles = roles.offset((page - 1) * 100).limit(page * 100)
        return jsonify({
            'results': [entry.to_dict() for entry in roles],
            'pagination': {
                'more': total_results > page * 100
            }
        })

    return jsonify([role.to_dict() for role in roles])
