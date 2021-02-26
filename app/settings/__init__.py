from flask import Blueprint

bp_api_admin = Blueprint('settings_api_admin', __name__,
                         url_prefix='/api/v1/admin/setting')
bp_client_admin = Blueprint('settings_client_admin', __name__,
                            url_prefix='/admin/settings',
                            template_folder='templates')

def register_blueprints(flask_app):
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_client_admin)
