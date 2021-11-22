''' Client routes for PV Stats related activities '''
from flask import abort, render_template, send_file
from flask_security import login_required, roles_required

from .. import bp_client_admin, bp_client_user

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    '''Returns static files for PV Stats module'''
    try:
        return send_file(f"modules/pv_stats/static/{file}")
    except:
        abort(404)

@bp_client_admin.route('/permissions')
@roles_required('admin')
def admin_get_pv_stats_nodes_permissions():
    '''PV Stats nodes management'''
    return render_template('admin_pv_stats_permissions.html')

@bp_client_user.route('/')
@login_required
def user_get_pv_stats():
    '''PV Stats'''
    return render_template('user_pv_stats.html')
