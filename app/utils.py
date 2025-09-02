# app/utils.py
import re
from datetime import date, datetime
from typing import List, Optional
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

# NUEVO: helpers de etiquetas
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


#Para la API de mercados
def rolling_insert_30(session, symbol: str, date_str: str, close: float, ModelDaily):
    exists = session.query(ModelDaily).filter_by(symbol=symbol, date=date_str).first()
    if exists:
        return
    row = ModelDaily(symbol=symbol, date=date_str, close=close)
    session.add(row)
    session.flush()
    rows = (session.query(ModelDaily)
                  .filter_by(symbol=symbol)
                  .order_by(ModelDaily.date.asc())
                  .all())
    if len(rows) > 30:
        for r in rows[:len(rows)-30]:
            session.delete(r)

def pct_change_n(series: list[float], n: int) -> Optional[float]:
    if len(series) <= n:
        return None
    curr = series[-1]; prev = series[-1-n]
    if prev == 0:
        return None
    return (curr - prev) / prev * 100.0
