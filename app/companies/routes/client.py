from flask import Response, abort, render_template, send_file
from flask_security import roles_required

from app.purchase.models.company import Company
from app.companies import bp_client_admin, bp_client_user

@bp_client_admin.route('/static/<path:file>')
@bp_client_user.route('/static/<path:file>')
def get_static(file):
    return send_file(f"companies/static/{file}")

@bp_client_admin.route('/')
@roles_required('admin')
def get_company():
    '''
    company management
    '''
    return render_template('companies.html')
