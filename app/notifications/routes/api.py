''' Notifications API routes '''
from datetime import datetime
from flask import jsonify, request
from flask_security import current_user, login_required, roles_required

from app import db
from app.tools import modify_object, prepare_datatables_query
from .. import bp_api_admin, bp_api_user
from ..models.notification import Notification

@bp_api_admin.route('', methods=['POST'])
@roles_required('admin')
def admin_create_notification():
    payload = request.get_json()
    if payload is None:
        return jsonify({'error': 'No payload'})
    notification = Notification(**payload, when_created=datetime.now())
    db.session.add(notification)
    db.session.commit()
    return jsonify({
        'data': notification.to_dict()
    })

@bp_api_admin.route('/<notification_id>', methods=['POST'])
@roles_required('admin')
def admin_update_notification(notification_id):
    notification = Notification.query.get(notification_id)
    if notification is None:
        return jsonify({'error': f'No notification is found by ID {notification_id}'})
    payload = request.get_json()
    if payload is None:
        return jsonify({'error': 'No payload'})
    modify_object(notification, payload, ['short_desc', 'long_desc'])
    db.session.commit()
    return jsonify({
        'data': notification.to_dict()
    })

@bp_api_admin.route('/<notification_id>', methods=['DELETE'])
@roles_required('admin')
def admin_delete_notification(notification_id):
    notification = Notification.query.get(notification_id)
    if notification is None:
        return jsonify({'error': f'No notification is found by ID {notification_id}'})
    db.session.delete(notification)
    db.session.commit()
    return jsonify({})
    
@bp_api_admin.route('', defaults={'notification_id': None})
@bp_api_admin.route('/<notification_id>')
@roles_required('admin')
def admin_get_notifications(notification_id):
    notifications = Notification.query
    if notification_id:
        notifications = notifications.filter_by(id=notification_id)
    if request.values.get('draw') is not None: # Args were provided by DataTables
        return _filter_notifications(notifications, request.values)

def _filter_notifications(notifications, filter_params):
    notifications, records_total, records_filtered = prepare_datatables_query(
        notifications, filter_params, None
    )
    return jsonify({
        'draw': int(filter_params['draw']),
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': [entry.to_dict(details=True) for entry in notifications]
    })

@bp_api_user.route('')
@login_required
def user_get_notifications():
    last_read_notification = current_user.get_profile().get('last_read_notification', 0)
    notifications = Notification.query.\
        filter(Notification.id > last_read_notification)
    return jsonify([notification.to_dict() for notification in notifications])

@bp_api_user.route('/<int:notification_id>', methods=['PUT'])
@login_required
def user_manage_notification(notification_id):
    if request.values.get('action') == 'mark_read':
        user_profile = current_user.get_profile()
        if int(user_profile.get('last_read_notification', 0)) < notification_id:
            user_profile['last_read_notification'] = notification_id
            current_user.set_profile(user_profile)
            db.session.commit()
    return jsonify({})