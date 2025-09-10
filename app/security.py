# app/security.py
from functools import wraps
from flask import abort
from flask_login import login_required, current_user

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.has_role(*roles):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def is_admin() -> bool:
    return current_user.is_authenticated and current_user.has_role('admin')

def can_manage_comment(c) -> bool:
    if not current_user.is_authenticated:
        return False
    # dueño por user_id o email, o admin
    return is_admin() or (getattr(c, "user_id", None) == current_user.id) or (c.correo == current_user.email)

def valid_password(pw: str) -> bool:
    return isinstance(pw, str) and len(pw) >= 8
