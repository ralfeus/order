import logging
from flask import current_app, request
from flask_security import current_user

def add_notification_block():
    logger = logging.getLogger('add_notification_block')
    if not request.full_path.startswith('/api') and \
        not request.full_path.startswith('/admin') and \
        not request.full_path.__contains__('/static/') and \
        not request.full_path.startswith('/favicon.ico') and \
        not request.full_path.startswith('/_debug_toolbar'):
        logger.debug(request.full_path)
        from app.notifications.models.notification import Notification
        last_read_notification = current_user.get_profile().get('last_read_notification', 0) \
            if not current_user.is_anonymous else 0
        unread_notifications = Notification.query.\
            filter(Notification.id > last_read_notification).count()
        logger.debug("There are %s unread notifications for %s",
            unread_notifications, current_user)
        current_app.jinja_env.globals.update(
            extension_1='badge.jinja',
            notifications=unread_notifications)
