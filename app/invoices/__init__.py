from flask import Blueprint

bp_api_user = Blueprint('invoices_api_user', __name__, url_prefix='/api/v1/invoice')
bp_api_admin = Blueprint('invoices_api_admin', __name__, url_prefix='/api/v1/admin/invoice')
bp_client_user = Blueprint('invoices_client_user', __name__, url_prefix='/invoices',
                           template_folder='templates')
bp_client_admin = Blueprint('invoices_client_admin', __name__, url_prefix='/admin/invoices',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)

