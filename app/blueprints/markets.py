# app/blueprints/markets.py

from datetime import datetime, timezone, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user, login_required
from app.extensions import db
from app.models import SiteNote, Role  # SiteNote(key, content, updated_at, author_id) y Role.admin
from app.markets import td_price_batch, td_timeseries_daily  # ← usa tus funciones EIA

bp = Blueprint("markets", __name__)

# Contenido inicial si la nota aún no existe (para que no salga vacío)
_INITIAL_CONTENT = (
    "Sin comentario aún. (Usa el botón “Nuevo comentario mercados” para publicar el primero.)"
)

def _ensure_singleton_note():
    """
    Garantiza que exista la fila única key='markets'.
    Si no existe, la crea con contenido inicial y fecha actual.
    Devuelve la instancia de SiteNote.
    """
    note = SiteNote.query.get("markets")
    if note is None:
        note = SiteNote(
            key="markets",
            content=_INITIAL_CONTENT,
            updated_at=datetime.now(timezone.utc),
            author_id=(current_user.id if getattr(current_user, "is_authenticated", False) else None),
        )
        db.session.add(note)
        db.session.commit()
    return note

@bp.get("/mercados")
def mercados_home():
    note = _ensure_singleton_note()
    date_str = note.updated_at.strftime("%d/%m/%Y") if note.updated_at else None
    return render_template(
        "mercados.html",
        markets_note=note.content or "",
        markets_note_date=date_str,
    )

def _pct_change(last, base):
    try:
        if last is None or base is None or float(base) == 0:
            return None
        return (float(last) - float(base)) / float(base) * 100.0
    except Exception:
        return None

def _extract_vals(ts_json):
    """Devuelve (dates_desc, closes_desc) tal como vienen del helper (orden descendente)."""
    vals = (ts_json or {}).get("values") or []
    dates = [str(v.get("datetime", ""))[:10] for v in vals if v.get("datetime")]
    closes = [v.get("close") for v in vals]
    return dates, closes

# ← Este endpoint es el que necesita tu plantilla: {{ url_for('markets.mercados_json') }}
@bp.get("/mercados/dashboard.json", endpoint="mercados_json")
def mercados_json():
    """
    Devuelve la estructura que espera el front:
    {
      "markets": [
        {
          "id": "brent" | "wti",
          "value": 67.8,
          "unit": "USD/bbl",
          "chg_10d_pct": -1.23,
          "chg_30d_pct": 2.34,
          "stale": false,
          "last_date": "YYYY-MM-DD",
          "spark_dates": ["YYYY-MM-DD", ...] (asc),
          "spark": [..precios..] (asc)
        },
        ...
      ]
    }
    """
    # Permitimos pasar alias por query; por defecto mostramos Brent/WTI
    syms_csv = request.args.get("s", "RBRTE,RWTC")

    # 1) Precios puntuales (strings en el helper) y series (30 puntos recientes)
    prices = td_price_batch(syms_csv)
    series_map = {}
    for raw in [s.strip() for s in syms_csv.split(",") if s.strip()]:
        series_map[raw] = td_timeseries_daily(raw, outputsize=32)

    # 2) Función para construir cada tarjeta (brent/wti)
    def _mk_market(id_key: str, price_key: str):
        # Precio puntual -> float
        p_obj = (prices.get(price_key) or {})
        p_val = p_obj.get("price")
        try:
            value = float(p_val) if p_val is not None else None
        except Exception:
            value = None

        # Serie descendente (más reciente primero)
        ts = series_map.get(price_key) or {}
        dates_desc, closes_desc = _extract_vals(ts)

        # Para spark, el front quiere ASCENDENTE
        spark_dates = list(reversed(dates_desc))
        spark = [float(x) if x is not None else None for x in reversed(closes_desc)]

        # Último dato (si hay)
        last_date = dates_desc[0] if dates_desc else None
        last_close = float(closes_desc[0]) if closes_desc and closes_desc[0] is not None else None

        # Cambios % a ~10 y ~30 observaciones atrás (si existen)
        base10 = float(closes_desc[10]) if len(closes_desc) > 10 and closes_desc[10] is not None else None
        base30 = float(closes_desc[30]) if len(closes_desc) > 30 and closes_desc[30] is not None else None
        chg10 = _pct_change(last_close, base10)
        chg30 = _pct_change(last_close, base30)

        # Staleness: si el último dato es de hace >10 días
        stale = False
        if last_date:
            try:
                y, m, d = [int(x) for x in last_date.split("-")]
                delta_days = (date.today() - date(y, m, d)).days
                stale = delta_days > 10
            except Exception:
                stale = False

        return {
            "id": id_key,
            "value": value,
            "unit": "USD/bbl",
            "chg_10d_pct": chg10,
            "chg_30d_pct": chg30,
            "stale": stale,
            "last_date": last_date,
            "spark_dates": spark_dates,
            "spark": spark,
        }

    # 3) Mapear claves de entrada a tarjetas esperadas por el front
    def _find_key(*candidates):
        for c in candidates:
            if c in prices:
                return c
        # si nada coincide, devuelve el primero (el front manejará None)
        return candidates[0]

    key_brent = _find_key("BRENT", "RBRTE")
    key_wti   = _find_key("WTI", "RWTC")

    payload = {
        "markets": [
            _mk_market("brent", key_brent),
            _mk_market("wti", key_wti),
        ]
    }
    return jsonify(payload)

# IMPORTANTÍSIMO: endpoint="update_markets_note" para que coincida con url_for('markets.update_markets_note')
@bp.route("/admin/markets-note", methods=["POST"], endpoint="update_markets_note")
@login_required
def update_markets_note():
    # Solo administradores
    if current_user.role != Role.admin:
        abort(403)

    content = (request.form.get("content") or "").strip()
    if not content:
        flash("Escribe el comentario antes de guardar.", "warning")
        return redirect(url_for("markets.mercados_home"))

    note = SiteNote.query.get("markets")
    if note is None:
        note = SiteNote(key="markets")
        db.session.add(note)

    note.content = content
    note.author_id = current_user.id
    # onupdate debería manejarlo; por si acaso, seteamos explícitamente:
    note.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    flash("Comentario de mercados actualizado.", "success")
    return redirect(url_for("markets.mercados_home"))
