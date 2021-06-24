from flask import Blueprint

bp_api_user = Blueprint('companies_api_user', __name__, url_prefix='/api/v1/company')
bp_api_admin = Blueprint('companies_api_admin', __name__, url_prefix='/api/v1/admin/company')
bp_client_user = Blueprint('companies_client_user', __name__, url_prefix='/companies',
                           template_folder='templates')
bp_client_admin = Blueprint('companies_client_admin', __name__, url_prefix='/admin/companies',
                            template_folder='templates')


def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)


