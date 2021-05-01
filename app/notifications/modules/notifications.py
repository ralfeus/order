from flask import Flask, request
from flask_security import current_user

def init(app: Flask):
    @app.before_request
    def add_notification_block():
        if not request.full_path.startswith('/api') and \
           not request.full_path.startswith('/admin'):
            from app.notifications.models.notification import Notification
            last_read_notification = current_user.get_profile().get('last_read_notification', 0) \
                if not current_user.is_anonymous else 0
            unread_notifications = Notification.query.\
                filter(Notification.id > last_read_notification).count()
            app.jinja_env.globals.update(
                extension_1='badge.jinja',
                notifications=unread_notifications)
