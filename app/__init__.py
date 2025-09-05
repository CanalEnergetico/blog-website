# app/__init__.py
from flask import Flask
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db, ckeditor
from .routes import bp
from .models import User
from .context import register_context
import logging, sys
from .errors import init_error_handlers

login_manager = LoginManager()
login_manager.login_view = "main.login"   # redirige a /login cuando haga falta
login_manager.login_message_category = "warning"

def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    login_manager.init_app(app)

    @app.after_request
    def _force_utf8(resp):
        if resp.mimetype == "text/html":
            ct = resp.headers.get("Content-Type", "")
            if "charset=" not in ct:
                resp.headers["Content-Type"] = f"{resp.mimetype}; charset=utf-8"
        return resp

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    try:
        from flask_compress import Compress
        Compress(app)
    except Exception:
        pass

    db.init_app(app)
    ckeditor.init_app(app)
    register_context(app)
    app.register_blueprint(bp)
    init_error_handlers(app)

    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    return app
