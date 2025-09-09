# app/auth_tokens.py
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

def _signer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)

# ---------- Verificación de email ----------
def gen_email_token(email: str) -> str:
    return _signer("email-verify").dumps({"email": email})

def verify_email_token(token: str, max_age=60*60*24*2):  # 48 h
    try:
        data = _signer("email-verify").loads(token, max_age=max_age)
        return data.get("email")
    except (BadSignature, SignatureExpired):
        return None

# ---------- Reset de contraseña ----------
def gen_reset_token(email: str) -> str:
    return _signer("password-reset").dumps({"email": email})

def verify_reset_token(token: str, max_age=60*60*2):  # 2 h
    try:
        data = _signer("password-reset").loads(token, max_age=max_age)
        return data.get("email")
    except (BadSignature, SignatureExpired):
        return None
