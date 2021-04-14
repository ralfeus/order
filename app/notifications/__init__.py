''' Module initialization '''
from flask import Blueprint

bp_api_user = Blueprint('addresses_api_user', __name__, url_prefix='/api/v1/notification')
bp_api_admin = Blueprint('addresses_api_admin', __name__,
                         url_prefix='/api/v1/admin/notification')
# bp_client_user = Blueprint('addresses_client_user', __name__, url_prefix='/notifications',
#                            template_folder='templates')
bp_client_admin = Blueprint('addresses_client_admin', __name__,
                            url_prefix='/admin/notifications',
                            template_folder='templates')

def register_blueprints(flask_app):
    ''' Register blueprints '''
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    # flask_app.register_blueprint(bp_client_user)
