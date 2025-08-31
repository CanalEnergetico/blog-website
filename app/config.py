import os
from dotenv import load_dotenv

load_dotenv(override=True)

def _get_db_url():
    url = os.getenv("DB_CANAL_URI") or os.getenv("DATABASE_URL") or ""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

class Config:
    SECRET_KEY = os.getenv("CANAL_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = _get_db_url() or "sqlite:///instance/dev.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SEND_FILE_MAX_AGE_DEFAULT = 86400

    TWELVEDATA_API_KEY = "716563acebdc49f9bbadd67d43692952"
    TWELVEDATA_SYMBOLS = {
        "brent": "XBR/USD",
        "wti":   "WTI/USD",
    }
