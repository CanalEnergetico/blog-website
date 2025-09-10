# app/blueprints/__init__.py
from .main import bp as main_bp
from .blog import bp as blog_bp
from .comments import bp as comments_bp
from .auth import bp as auth_bp
from .markets import bp as markets_bp
from .meta import bp as meta_bp

__all__ = ["main_bp", "blog_bp", "comments_bp", "auth_bp", "markets_bp", "meta_bp"]
