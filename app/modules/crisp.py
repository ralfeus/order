from flask.app import Flask


def init(app: Flask):
    with app.app_context():
        from app.settings.models.setting import Setting
        crisp_id = Setting.query.get('crisp.id')
        app.jinja_env.globals['crisp_id'] = crisp_id.value \
            if crisp_id else None