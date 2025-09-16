# app/blueprints/markets.py

from datetime import datetime, timezone
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

# ← Este endpoint es el que necesita tu plantilla: {{ url_for('markets.mercados_json') }}
@bp.get("/mercados/dashboard.json", endpoint="mercados_json")
def mercados_json():
    """
    Devuelve precios y series para el dashboard de mercados.
    Usa 's' en querystring para elegir símbolos (por defecto RBRTE,RWTC).
    """
    syms_csv = request.args.get("s", "RBRTE,RWTC")
    # precios actuales (mantiene claves de entrada)
    prices = td_price_batch(syms_csv)

    # series recientes (por defecto 30 puntos)
    series = {}
    for raw in [s.strip() for s in syms_csv.split(",") if s.strip()]:
        series[raw] = td_timeseries_daily(raw, outputsize=30)

    return jsonify({"prices": prices, "series": series})

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
