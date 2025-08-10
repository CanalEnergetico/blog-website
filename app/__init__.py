# app/__init__.py
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db, ckeditor
from .routes import bp
from .context import register_context
import logging, sys
from .errors import init_error_handlers


def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

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

    return app
