from flask import Flask

def init(app: Flask):
    @app.before_request
    def set_crisp_id():
        with app.app_context():
            from app.settings.models.setting import Setting
            crisp_id = Setting.query.get('crisp.id')
            app.jinja_env.globals.update(
                crisp_id=crisp_id.value if crisp_id else None)
