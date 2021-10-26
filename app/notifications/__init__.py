''' Module initialization '''
from flask import Blueprint
from .signal_handlers import add_notification_block

bp_api_user = Blueprint('notifications_api_user', __name__, url_prefix='/api/v1/notification')
bp_api_admin = Blueprint('notifications_api_admin', __name__,
                         url_prefix='/api/v1/admin/notification')
bp_client_admin = Blueprint('notifications_client_admin', __name__,
                            url_prefix='/admin/notifications',
                            template_folder='templates')
bp_client_user = Blueprint('notifications_client_user', __name__,
                            url_prefix='/notifications')

def register_blueprints(flask_app):
    ''' Register blueprints '''
    from . import routes
    flask_app.register_blueprint(bp_api_admin)
    flask_app.register_blueprint(bp_api_user)
    flask_app.register_blueprint(bp_client_admin)
    flask_app.register_blueprint(bp_client_user)
    _register_signals(flask_app)

def _register_signals(app):
    app.before_request(add_notification_block)
