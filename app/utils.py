# app/utils.py
import re
from datetime import date, datetime
from typing import List
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

# ---------------------------
# NUEVO: helpers de etiquetas
# ---------------------------
def parse_tags(cadena: str | None) -> List[str]:
    """
    Convierte 'python, flask; AI  #web' -> ['python', 'flask', 'AI', 'web']
    - separa por comas o punto y coma
    - quita espacios y '#'
    - dedup case-insensitive preservando el primero
    """
    if not cadena:
        return []
    partes = re.split(r"[;,]", cadena)
    limpio, vistos = [], set()
    for p in (x.strip().lstrip("#") for x in partes):
        if not p:
            continue
        k = p.lower()
        if k not in vistos:
            vistos.add(k)
            limpio.append(p)
    return limpio

def tag_slug(nombre: str) -> str:
    # Puedes usar la misma lib que ya usas para slugs de artículos
    return slugify(nombre)
