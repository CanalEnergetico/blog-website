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
    WTF_CSRF_ENABLED = True
    # Seguridad / token para el endpoint de refresh
    SECRET_KEY = os.getenv("CANAL_KEY", "dev-secret")
    CANAL_KEY  = os.getenv("CANAL_KEY", "")

    # Base de datos
    SQLALCHEMY_DATABASE_URI = _get_db_url() or "sqlite:///instance/dev.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies / static
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SEND_FILE_MAX_AGE_DEFAULT = 86400  # 1 día

    # === Claves de APIs ===
    # TwelveData (la dejamos por compatibilidad, aunque no la usemos)
    TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")

    # EIA (US Energy Information Administration) - GRATIS
    # Añade EIA_API_KEY=... en tu .env
    EIA_API_KEY = os.getenv("EIA_API_KEY", "")

    # === Símbolos de "mercados" ===
    # Para "disfrazar" la EIA sin tocar rutas/plantillas:
    # usamos los códigos diarios de la EIA (series "RBRTE" y "RWTC").
    # Tu markets.py adaptado a EIA tomará estos como símbolos.
    TWELVEDATA_SYMBOLS = {
        "brent": "RBRTE",  # Brent (PET.RBRTE.D)
        "wti":   "RWTC",   # WTI  (PET.RWTC.D)
    }

    ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

    PASSWORD_RESET_SALT = os.getenv("PASSWORD_RESET_SALT", "cambia-esta-sal")
    PASSWORD_RESET_EXP_SECS = int(os.getenv("PASSWORD_RESET_EXP_SECS", "3600"))

    # Configuración de correo
    MAIL_SENDER = os.getenv("MAIL_SENDER")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")


