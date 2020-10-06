from flask import Blueprint

bp_api_user = Blueprint('purchase_api_user', __name__, url_prefix='/api/v1/purchase')
bp_api_admin = Blueprint('purchase_api_admin', __name__, url_prefix='/api/v1/admin/purchase')
bp_client_user = Blueprint('purchase_client_user', __name__, url_prefix='/purchase',
                           template_folder='templates')
bp_client_admin = Blueprint('purchase_client_admin', __name__, url_prefix='/admin/purchase',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
