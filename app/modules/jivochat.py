from flask import Flask, request

def init(app: Flask):
    @app.before_request
    def set_jivochat_id():
        if not request.full_path.startswith('/api'):
            from app import db
            from app.settings.models.setting import Setting
            jivochat_id = db.session.get(Setting, 'jivochat.id')
            app.jinja_env.globals.update(
                jivochat_id=jivochat_id.value if jivochat_id else None)
            # pass