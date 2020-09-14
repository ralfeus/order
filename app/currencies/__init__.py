from flask import Blueprint

bp_api_user = Blueprint('curencies_api_user', __name__, url_prefix='/api/v1/curency')
bp_api_admin = Blueprint('curencies_api_admin', __name__, url_prefix='/api/v1/admin/curency')
bp_client_user = Blueprint('curencies_client_user', __name__, url_prefix='/curencies',
                           template_folder='templates')
bp_client_admin = Blueprint('curencies_client_admin', __name__, url_prefix='/admin/curencies',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)

import app.curencies.routes.api
import app.curencies.routes.client
