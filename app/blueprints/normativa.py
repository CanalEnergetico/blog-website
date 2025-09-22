from flask import Blueprint, render_template, request, jsonify, abort, current_app, redirect, url_for, flash
import math
from sqlalchemy import text
from datetime import datetime
from app.extensions import db
from flask_login import login_required, current_user
from app.models import Role
from app.utils_mail import send_email

bp = Blueprint("normativa", __name__)

# Helperss
def _build_where_and_params(q: str, tema: str, anio: str, institucion: str, tipo: str):
    where, params = [], {}
    if q:
        where.append("to_tsvector('spanish', coalesce(titulo_oficial,'') || ' ' || coalesce(descripcion,'')) @@ plainto_tsquery('spanish', :q)")
        params["q"] = q
    if tema: where.append("tema = :tema"); params["tema"] = tema
    if anio:
        try: params["anio"] = int(anio); where.append("anio = :anio")
        except: pass
    if institucion: where.append("institucion = :institucion"); params["institucion"] = institucion
    if tipo: where.append("tipo = :tipo"); params["tipo"] = tipo
    return ("WHERE " + " AND ".join(where)) if where else "", params

def _order_clause(orden: str) -> str:
    return "ORDER BY titulo_oficial ASC NULLS LAST" if orden == "az" else "ORDER BY fecha_publicacion DESC NULLS LAST, titulo_oficial ASC"

def _slugify(s: str) -> str:
    import re, unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+","-",s).strip("-"); s = re.sub(r"-{2,}","-",s)
    return s or "norma"

def _unique_slug(base: str) -> str:
    slug, i = base, 2
    while True:
        if not db.session.execute(text("select 1 from normativa where slug_url = :s limit 1"), {"s": slug}).first():
            return slug
        slug = f"{base}-{i}"; i += 1

def _unique_slug_excluding(base: str, exclude_id: int) -> str:
    slug, i = base, 2
    while True:
        row = db.session.execute(text("select id from normativa where slug_url = :s limit 1"), {"s": slug}).first()
        if not row or (row.id == exclude_id):
            return slug
        slug = f"{base}-{i}"; i += 1

def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u: return ""
    return u if u.startswith(("http://","https://")) else "https://" + u

# Routes
@bp.get("/normativa")
def list():
    return render_template("normativa.html")

@bp.get("/normativa/api/list", endpoint="list_json")
def list_json():
    q  = (request.args.get("q") or "").strip()
    tema = (request.args.get("tema") or "").strip()
    anio = (request.args.get("anio") or "").strip()
    inst = (request.args.get("institucion") or "").strip()
    tipo = (request.args.get("tipo") or "").strip()
    orden = (request.args.get("orden") or "recientes").strip()
    try: page = int(request.args.get("page","1"))
    except: page = 1

    PER_PAGE = 12
    page = max(1, page)
    where_sql, params = _build_where_and_params(q, tema, anio, inst, tipo)
    order_sql = _order_clause(orden)

    try:
        total = int(db.session.execute(text(f"SELECT count(*)::bigint AS c FROM normativa {where_sql}"), params).first().c or 0)
    except Exception:
        current_app.logger.exception("Error contando normativa")
        return jsonify({"items": [], "page": 1, "total_pages": 1})
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = min(page, total_pages); offset = (page - 1) * PER_PAGE

    sql_list = text(f"""
        SELECT id, slug_url, titulo_oficial, fecha_publicacion, anio, institucion, tipo, tema, descripcion, enlace_oficial, pdf_url
        FROM normativa {where_sql} {order_sql} LIMIT :limit OFFSET :offset
    """)
    try:
        rows = db.session.execute(sql_list, {**params, "limit": PER_PAGE, "offset": offset}).mappings().all()
        items = [dict(r) for r in rows]
    except Exception:
        current_app.logger.exception("Error consultando normativa")
        return jsonify({"items": [], "page": 1, "total_pages": 1})
    return jsonify({"items": items, "page": page, "total_pages": total_pages})

@bp.post("/normativa/sugerir", endpoint="suggest")
def suggest():
    nombre = (request.form.get("nombre") or "").strip()
    url = _normalize_url(request.form.get("url"))
    comentario = (request.form.get("comentario") or "").strip()
    correo = (request.form.get("correo") or "").strip()
    if not nombre or not url: abort(400, description="Faltan campos obligatorios.")
    to_email = current_app.config.get("MAIL_RECIPIENT_NORMATIVA") or current_app.config.get("MAIL_SENDER")
    html = f"""
      <h2>Nueva sugerencia de normativa</h2>
      <p><strong>Nombre:</strong> {nombre}</p>
      <p><strong>URL:</strong> <a href="{url}" target="_blank" rel="noopener">{url}</a></p>
      <p><strong>Comentario:</strong><br>{(comentario or '—')}</p>
      <p><strong>Correo de contacto (opcional):</strong> {(correo or '—')}</p>
      <hr><p style="color:#888">Canal Energético – formulario de sugerencias</p>
    """.strip()
    try:
        send_email(to_email=to_email, subject="Nueva sugerencia de normativa", html=html)
    except Exception:
        current_app.logger.exception("Error enviando sugerencia de normativa")
        abort(500, description="No se pudo enviar la sugerencia. Intenta más tarde.")
    return ("", 204)

@bp.post("/normativa/admin/create", endpoint="admin_create")
@login_required
def admin_create():
    if current_user.role != Role.admin: abort(403)
    titulo = (request.form.get("titulo_oficial") or "").strip()
    if not titulo:
        flash("El título oficial es obligatorio.", "warning"); return redirect(url_for("normativa.list"))
    fecha_raw = (request.form.get("fecha_publicacion") or "").strip()
    try: fecha_dt = datetime.strptime(fecha_raw, "%Y-%m-%d").date() if fecha_raw else None
    except ValueError:
        flash("La fecha de publicación debe tener formato YYYY-MM-DD.", "warning"); return redirect(url_for("normativa.list"))

    slug = (request.form.get("slug_url") or "").strip() or _slugify(titulo)
    slug = _unique_slug(slug)
    params = {
        "slug_url": slug,
        "titulo_oficial": titulo,
        "fecha_publicacion": fecha_dt,
        "institucion": (request.form.get("institucion") or "").strip() or None,
        "tipo": (request.form.get("tipo") or "").strip() or None,
        "tema": (request.form.get("tema") or "").strip() or None,
        "descripcion": (request.form.get("descripcion") or "").strip() or None,
        "enlace_oficial": _normalize_url(request.form.get("enlace_oficial")),
        "pdf_url": _normalize_url(request.form.get("pdf_url")),
    }
    sql = text("""
        INSERT INTO normativa (slug_url, titulo_oficial, fecha_publicacion, institucion, tipo, tema, descripcion, enlace_oficial, pdf_url, created_at, updated_at)
        VALUES (:slug_url, :titulo_oficial, :fecha_publicacion, :institucion, :tipo, :tema, :descripcion, :enlace_oficial, :pdf_url, now(), now())
        RETURNING id
    """)
    try:
        db.session.execute(sql, params).first(); db.session.commit()
        flash("Normativa creada correctamente.", "success")
    except Exception:
        db.session.rollback(); current_app.logger.exception("Error creando normativa")
        flash("No se pudo crear la normativa. Revisa los datos.", "danger")
    return redirect(url_for("normativa.list"))

@bp.post("/normativa/admin/edit", endpoint="admin_edit")
@login_required
def admin_edit():
    if current_user.role != Role.admin: abort(403)
    try: nid = int((request.form.get("id") or "").strip())
    except: flash("ID inválido.", "warning"); return redirect(url_for("normativa.list"))

    row = db.session.execute(text("SELECT id FROM normativa WHERE id = :id"), {"id": nid}).first()
    if not row: flash("No se encontró la normativa.", "warning"); return redirect(url_for("normativa.list"))

    titulo = (request.form.get("titulo_oficial") or "").strip()
    if not titulo: flash("El título oficial es obligatorio.", "warning"); return redirect(url_for("normativa.list"))

    fecha_raw = (request.form.get("fecha_publicacion") or "").strip()
    try: fecha_dt = datetime.strptime(fecha_raw, "%Y-%m-%d").date() if fecha_raw else None
    except ValueError:
        flash("La fecha de publicación debe tener formato YYYY-MM-DD.", "warning"); return redirect(url_for("normativa.list"))

    slug_candidate = (request.form.get("slug_url") or "").strip()
    base_slug = _slugify(slug_candidate or titulo)
    slug = _unique_slug_excluding(base_slug, exclude_id=nid)

    params = {
        "id": nid,
        "slug_url": slug,
        "titulo_oficial": titulo,
        "fecha_publicacion": fecha_dt,
        "institucion": (request.form.get("institucion") or "").strip() or None,
        "tipo": (request.form.get("tipo") or "").strip() or None,
        "tema": (request.form.get("tema") or "").strip() or None,
        "descripcion": (request.form.get("descripcion") or "").strip() or None,
        "enlace_oficial": _normalize_url(request.form.get("enlace_oficial")),
        "pdf_url": _normalize_url(request.form.get("pdf_url")),
    }
    sql = text("""
        UPDATE normativa SET
          slug_url=:slug_url, titulo_oficial=:titulo_oficial, fecha_publicacion=:fecha_publicacion,
          institucion=:institucion, tipo=:tipo, tema=:tema, descripcion=:descripcion,
          enlace_oficial=:enlace_oficial, pdf_url=:pdf_url, updated_at=now()
        WHERE id=:id RETURNING id
    """)
    try:
        res = db.session.execute(sql, params).first()
        if res: db.session.commit(); flash("Normativa actualizada.", "success")
        else: db.session.rollback(); flash("No se pudo actualizar.", "danger")
    except Exception:
        db.session.rollback(); current_app.logger.exception("Error editando normativa")
        flash("No se pudo actualizar la normativa.", "danger")
    return redirect(url_for("normativa.list"))

@bp.post("/normativa/admin/delete", endpoint="admin_delete")
@login_required
def admin_delete():
    if current_user.role != Role.admin: abort(403)
    nid = (request.form.get("id") or "").strip()
    if not nid:
        flash("ID no proporcionado.", "warning"); return redirect(url_for("normativa.list"))
    try:
        res = db.session.execute(text("DELETE FROM normativa WHERE id = :id RETURNING id"), {"id": nid}).first()
        if res: db.session.commit(); flash("Normativa eliminada.", "success")
        else: db.session.rollback(); flash("No se encontró la normativa indicada.", "warning")
    except Exception:
        db.session.rollback(); current_app.logger.exception("Error eliminando normativa")
        flash("No se pudo eliminar la normativa.", "danger")
    return redirect(url_for("normativa.list"))
