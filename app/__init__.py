# app/__init__.py
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db, ckeditor, migrate
from .context import register_context
from .errors import init_error_handlers
import logging, sys
from app.extensions import csrf  # ← usa la instancia única definida en app/extensions.py

login_manager = LoginManager()
# NO crear otra instancia aquí: csrf = CSRFProtect()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    # Middleware / logging
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

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)      # Alembic/Flask-Migrate después de db
    ckeditor.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)             # ← inicializa la instancia única importada

    # CSRF en plantillas ({{ csrf_token() }})
    app.jinja_env.globals['csrf_token'] = generate_csrf

    # Asegura que Alembic "vea" todos los modelos
    from . import models  # noqa: F401

    # Context processors y manejadores de error
    register_context(app)
    init_error_handlers(app)

    # Blueprints
    from .blueprints import main_bp, blog_bp, comments_bp, auth_bp, markets_bp, meta_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(markets_bp)
    app.register_blueprint(meta_bp)

    @app.after_request
    def _force_utf8(resp):
        if resp.mimetype == "text/html":
            ct = resp.headers.get("Content-Type", "")
            if "charset=" not in ct:
                resp.headers["Content-Type"] = f"{resp.mimetype}; charset=utf-8"
        return resp

    @login_manager.user_loader
    def load_user(user_id: str):
        from .models import User
        return User.query.get(int(user_id))

    return app
