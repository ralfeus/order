''' Notifications API routes '''
from flask import jsonify, request
from flask_security import roles_required

from app.tools import prepare_datatables_query
from .. import bp_client_admin
from ..models.notification import Notification

@bp_client_admin.route('', defaults={'notification_id': None})
@bp_client_admin.route('/<notification_id>')
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