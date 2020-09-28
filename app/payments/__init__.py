from flask import Blueprint

bp_api_user = Blueprint('transactions_api_user', __name__, 
                        url_prefix='/api/v1/transaction')
bp_api_admin = Blueprint('transactions_api_admin', __name__, 
                         url_prefix='/api/v1/admin/transaction')
bp_client_user = Blueprint('transactions_client_user', __name__, 
                           url_prefix='/transactions',
                           template_folder='templates')
bp_client_admin = Blueprint('transactions_client_admin', __name__, 
                            url_prefix='/admin/transactions',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
