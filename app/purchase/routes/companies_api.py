from datetime import datetime

from flask import Response, abort, jsonify, request
from flask_security import roles_required

from app import db
from app.purchase import bp_api_admin
from app.tools import modify_object

from ..validators.company import CompanyValidator
from app.purchase.models import Company


@bp_api_admin.route('/company', defaults={'company_id': None})
@bp_api_admin.route('/company/<company_id>')
@roles_required('admin')
def get_company(company_id):
    ''' Returns all or selected company in JSON '''
    company = Company.query
    if company_id is not None:
        company = company.filter_by(id=company_id)
        
    return jsonify([entry.to_dict() for entry in company])
    
@bp_api_admin.route('/company/<company_id>', methods=['POST'])
@bp_api_admin.route('/company', methods=['POST'], defaults={'company_id': None})
@roles_required('admin')
def save_company(company_id):
    ''' Creates or modifies existing company '''
    with CompanyValidator(request) as validator:
        if not validator.validate():
            return jsonify({
                'data': [],
                'error': "Couldn't save a company",
                'fieldErrors': [{'name': message.split(':')[0], 'status': message.split(':')[1]}
                                for message in validator.errors]
            })
    payload = request.get_json()
    company = None
    if company_id is None:
        company = Company()
        company.when_created = datetime.now()
        db.session.add(company)
    else:
        company = Company.query.get(company_id)
        if not company:
            abort(Response(f'No company <{company_id}> was found', status=400))

    if payload.get('tax_id') is None or payload['tax_id'] == '':
        payload['tax_id_1'] = payload['tax_id_2'] = payload['tax_id_3'] = ''
    else:
        payload['tax_id_1'], payload['tax_id_2'], payload['tax_id_3'] = payload['tax_id'].split('-')
    if payload.get('address') is not None:
        payload['address_id'] = payload['address']['id']
    if payload.get('tax_address') is not None:
        payload['tax_address_id'] = payload['tax_address']['id']
    default_company = Company.query.filter_by(default=True).first()
    if payload.get('default', False):
        if default_company is not None:
            default_company.default = False
        company.default = True
    modify_object(company, payload,
        ['name', 'contact_person', 'tax_id_1', 'tax_id_2', 'tax_id_3', 'phone',
         'address_id', 'bank_id', 'tax_simplified', 'tax_phone', 'tax_address_id',
         'business_type', 'business_category', 'email', 'enabled'])

    db.session.commit()
    if default_company is not None:
        result = [company.to_dict(), default_company.to_dict()]
    else:
        result = [company.to_dict()]
    return jsonify({'data': result})

@bp_api_admin.route('/company/<company_id>', methods=['DELETE'])
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
    return jsonify({'status': 'success'})
