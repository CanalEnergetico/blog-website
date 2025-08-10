# app/utils.py
import re
from datetime import date, datetime
from slugify import slugify
from .models import Articulos

def generar_slug(titulo: str) -> str:
    base = slugify(titulo)
    slug = base
    n = 2
    while Articulos.query.filter_by(slug=slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug

def _parse_fecha(fecha_str: str) -> date:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha_str, fmt).date()
        except Exception:
            pass
    return date.today()

def plain_text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "")
