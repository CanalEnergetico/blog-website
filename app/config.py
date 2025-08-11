# app/config.py
import os
from dotenv import load_dotenv

# Carga .env muy pronto; override=True por si algo vino mal seteado
load_dotenv(override=True)

def _get_db_url():
    # Prioridad: DB_CANAL_URI (tuya) luego DATABASE_URL (de proveedores)
    url = os.getenv("DB_CANAL_URI") or os.getenv("DATABASE_URL") or ""
    # Normaliza prefijo antiguo de algunos proveedores
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # Opcional: fuerza driver psycopg si quieres (requiere psycopg instalado):
    # if url.startswith("postgresql://") and "+psycopg" not in url:
    #     url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

class Config:
    SECRET_KEY = os.getenv("CANAL_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = _get_db_url() or "sqlite:///instance/dev.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SEND_FILE_MAX_AGE_DEFAULT = 86400  # 1 día
