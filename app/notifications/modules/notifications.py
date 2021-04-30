from flask_security import AnonymousUser
from flask import Flask
from flask_security import current_user

def init(app: Flask):
    @app.before_request
    def add_notification_block():
        from app.notifications.models.notification import Notification
        last_read_notification = current_user.get_profile().get('last_read_notification', 0) \
            if not current_user.is_anonymous else 0
        unread_notifications = Notification.query.\
            filter(Notification.id > last_read_notification).count()
        app.jinja_env.globals.update(
            extension_1='badge.jinja',
            notifications=unread_notifications)
