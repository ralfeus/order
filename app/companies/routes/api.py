from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import login_required, roles_required

from app import db
from app.tools import modify_object
from app.companies import bp_api_admin, bp_api_user
from app.models.address import Address
from app.purchase.models.company import Company


@bp_api_admin.route('/', defaults={'company_id': None}, strict_slashes=False)
@bp_api_user.route('', defaults={'company_id': None})
@bp_api_admin.route('/<company_id>')
@bp_api_user.route('/<company_id>')
@login_required

def get_company(company_id):
    '''
    Returns all or selected company in JSON:
    '''
    company = Company.query.all() \
        if company_id is None \
        else Company.query.filter_by(id=company_id)
        
    return jsonify(list(map(lambda entry: entry.to_dict(), company)))
    
@bp_api_admin.route('/<company_id>', methods=['POST'])
@bp_api_admin.route('/', methods=['POST'], defaults={'company_id': None}, strict_slashes=False)
@roles_required('admin')
def save_company_item(company_id):
    '''
    Creates or modifies existing company
    '''
    payload = request.get_json()
    if not payload:
        abort(Response('No data was provided', status=400))

    if payload.get('id'):
        try:
            float(payload['id'])
        except: 
            abort(Response('Not number', status=400))

    company = None
    if company_id is None:
        company = Company()
        company.when_created = datetime.now()
        db.session.add(company)
    else:
        company = Company.query.get(company_id)
        if not company:
            abort(Response(f'No company <{company_id}> was found', status=400))

    # for key, value in payload.items():

    #     if getattr(company, key) != value:
    #         setattr(company, key, value)
    #         company.when_changed = datetime.now()
    payload['tax_id_1'], payload['tax_id_2'], payload['tax_id_3'] = payload['tax_id'].split('-')
    modify_object(company, payload, 
        ['name', 'contact_person', 'tax_id_1', 'tax_id_2', 'tax_id_3', 'phone',
         'address_id', 'bank_id'])

    db.session.commit()
    return jsonify(company.to_dict())


@bp_api_admin.route('/<company_id>', methods=['DELETE'])
@roles_required('admin')
def delete_company(company_id):
    '''
    Deletes existing company item
    '''
    company = Company.query.get(company_id)
    if not company:
        abort(Response(f'No company <{company_id}> was found', status=404))

    db.session.delete(company)
    db.session.commit()
    return jsonify({
        'status': 'success'
    })
