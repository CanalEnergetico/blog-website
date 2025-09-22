# app/blueprints/normativa.py

from flask import Blueprint, render_template, request, jsonify, abort, current_app, redirect, url_for, flash
import math
from sqlalchemy import text
from datetime import datetime
from app.extensions import db  # usa DB_CANAL_URI ya configurado
from flask_login import login_required, current_user
from app.models import Role  # mismo uso que en markets.py (Role.admin)
from app.utils_mail import send_email  # ← envío de correo con variables del .env

bp = Blueprint("normativa", __name__)

# ---------------------- Helpers (SQL, slugs, URL) ----------------------
def _build_where_and_params(q: str, tema: str, anio: str, institucion: str, tipo: str):
    """
    WHERE y parámetros para filtros y búsqueda.
    Usa to_tsvector/plainto_tsquery en español sobre (titulo_oficial + descripcion).
    """
    where = []
    params = {}

    if q:
        where.append(
            "to_tsvector('spanish', coalesce(titulo_oficial,'') || ' ' || coalesce(descripcion,'')) @@ plainto_tsquery('spanish', :q)"
        )
        params["q"] = q

    if tema:
        where.append("tema = :tema")
        params["tema"] = tema

    if anio:
        try:
            params["anio"] = int(anio)
            where.append("anio = :anio")
        except Exception:
            pass

    if institucion:
        where.append("institucion = :institucion")
        params["institucion"] = institucion

    if tipo:
        where.append("tipo = :tipo")
        params["tipo"] = tipo

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params


def _order_clause(orden: str) -> str:
    if orden == "az":
        return "ORDER BY titulo_oficial ASC NULLS LAST"
    return "ORDER BY fecha_publicacion DESC NULLS LAST, titulo_oficial ASC"


def _slugify(s: str) -> str:
    import re, unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s or "norma"


def _unique_slug(base_slug: str) -> str:
    """
    Asegura unicidad en normativa.slug_url
    """
    slug = base_slug
    i = 2
    while True:
        row = db.session.execute(
            text("select 1 from normativa where slug_url = :s limit 1"), {"s": slug}
        ).first()
        if not row:
            return slug
        slug = f"{base_slug}-{i}"
        i += 1


def _normalize_url(u: str) -> str:
    """
    Acepta 'google.com' o 'www.google.com' y antepone https:// si falta esquema.
    Devuelve '' si u está vacío.
    """
    u = (u or "").strip()
    if not u:
        return ""
    if u.startswith(("http://", "https://")):
        return u
    return "https://" + u


# ----------------------------- Rutas -----------------------------
@bp.get("/normativa")
def list():
    """Renderiza la vista con filtros + tarjetas (normativa.html)."""
    return render_template("normativa.html")


@bp.get("/normativa/api/list", endpoint="list_json")
def list_json():
    """
    Devuelve JSON con:
    { items: [...], page: N, total_pages: M }
    Filtros: q, tema, anio, institucion, tipo, orden, page
    """
    q            = (request.args.get("q") or "").strip()
    tema         = (request.args.get("tema") or "").strip()
    anio         = (request.args.get("anio") or "").strip()
    institucion  = (request.args.get("institucion") or "").strip()
    tipo         = (request.args.get("tipo") or "").strip()
    orden        = (request.args.get("orden") or "recientes").strip()
    try:
        page = int(request.args.get("page", "1"))
    except Exception:
        page = 1

    PER_PAGE = 12
    page = max(1, page)
    offset = (page - 1) * PER_PAGE

    where_sql, params = _build_where_and_params(q, tema, anio, institucion, tipo)
    order_sql = _order_clause(orden)

    # Total
    sql_count = text(f"""
        SELECT count(*)::bigint AS c
        FROM normativa
        {where_sql}
    """)
    try:
        res_count = db.session.execute(sql_count, params).first()
        total = int(res_count.c) if res_count and res_count.c is not None else 0
    except Exception:
        current_app.logger.exception("Error contando normativa")
        return jsonify({"items": [], "page": 1, "total_pages": 1}), 200

    total_pages = max(1, math.ceil(total / PER_PAGE))
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * PER_PAGE

    # Listado paginado
    sql_list = text(f"""
        SELECT
          id,
          slug_url,
          titulo_oficial,
          fecha_publicacion,
          anio,
          institucion,
          tipo,
          tema,
          descripcion,
          enlace_oficial,
          pdf_url
        FROM normativa
        {where_sql}
        {order_sql}
        LIMIT :limit OFFSET :offset
    """)
    params_list = dict(params)
    params_list.update({"limit": PER_PAGE, "offset": offset})

    try:
        rows = db.session.execute(sql_list, params_list).mappings().all()
        items = [dict(r) for r in rows]
    except Exception:
        current_app.logger.exception("Error consultando normativa")
        return jsonify({"items": [], "page": 1, "total_pages": 1}), 200

    return jsonify({
        "items": items,
        "page": page,
        "total_pages": total_pages
    })


@bp.post("/normativa/sugerir", endpoint="suggest")
def suggest():
    """
    Form '¿Falta alguna normativa?' – Envía correo usando utils_mail y variables del .env.
    To: MAIL_RECIPIENT_NORMATIVA (si existe) o MAIL_SENDER por defecto.
    """
    nombre = (request.form.get("nombre") or "").strip()
    url_raw = (request.form.get("url") or "").strip()
    comentario = (request.form.get("comentario") or "").strip()
    correo = (request.form.get("correo") or "").strip()  # opcional

    if not nombre or not url_raw:
        abort(400, description="Faltan campos obligatorios.")

    url = _normalize_url(url_raw)

    to_email = current_app.config.get("MAIL_RECIPIENT_NORMATIVA") or current_app.config.get("MAIL_SENDER")
    subject = "Nueva sugerencia de normativa"
    html = f"""
      <h2>Nueva sugerencia de normativa</h2>
      <p><strong>Nombre:</strong> {nombre}</p>
      <p><strong>URL:</strong> <a href="{url}" target="_blank" rel="noopener">{url}</a></p>
      <p><strong>Comentario:</strong><br>{(comentario or '—')}</p>
      <p><strong>Correo de contacto (opcional):</strong> {(correo or '—')}</p>
      <hr>
      <p style="color:#888">Canal Energético – formulario de sugerencias</p>
    """.strip()

    try:
        send_email(to_email=to_email, subject=subject, html=html)
    except Exception:
        current_app.logger.exception("Error enviando sugerencia de normativa")
        abort(500, description="No se pudo enviar la sugerencia. Intenta más tarde.")

    # Éxito (el front espera 204)
    return ("", 204)


@bp.post("/normativa/admin/create", endpoint="admin_create")
@login_required
def admin_create():
    """
    Crear una nueva normativa desde el modal (solo admin).
    Inserta en la tabla y deja que 'anio' se genere desde 'fecha_publicacion'.
    """
    # Autorización: solo administradores
    if current_user.role != Role.admin:
        abort(403)

    titulo_oficial    = (request.form.get("titulo_oficial") or "").strip()
    fecha_publicacion = (request.form.get("fecha_publicacion") or "").strip()  # YYYY-MM-DD
    institucion       = (request.form.get("institucion") or "").strip()
    tipo              = (request.form.get("tipo") or "").strip()
    tema              = (request.form.get("tema") or "").strip()
    descripcion       = (request.form.get("descripcion") or "").strip()
    enlace_oficial    = (request.form.get("enlace_oficial") or "").strip()
    pdf_url           = (request.form.get("pdf_url") or "").strip()
    slug_url          = (request.form.get("slug_url") or "").strip()

    if not titulo_oficial:
        flash("El título oficial es obligatorio.", "warning")
        return redirect(url_for("normativa.list"))

    # Parse fecha
    fecha_dt = None
    if fecha_publicacion:
        try:
            fecha_dt = datetime.strptime(fecha_publicacion, "%Y-%m-%d").date()
        except ValueError:
            flash("La fecha de publicación debe tener formato YYYY-MM-DD.", "warning")
            return redirect(url_for("normativa.list"))

    # Slug
    if not slug_url:
        slug_url = _slugify(titulo_oficial)
    slug_url = _unique_slug(slug_url)

    # Normaliza URLs
    enlace_oficial = _normalize_url(enlace_oficial)
    pdf_url = _normalize_url(pdf_url)

    sql = text("""
        INSERT INTO normativa
          (slug_url, titulo_oficial, fecha_publicacion, institucion, tipo, tema, descripcion, enlace_oficial, pdf_url, created_at, updated_at)
        VALUES
          (:slug_url, :titulo_oficial, :fecha_publicacion, :institucion, :tipo, :tema, :descripcion, :enlace_oficial, :pdf_url, now(), now())
        RETURNING id
    """)

    params = {
        "slug_url": slug_url,
        "titulo_oficial": titulo_oficial,
        "fecha_publicacion": fecha_dt,
        "institucion": institucion or None,
        "tipo": tipo or None,
        "tema": tema or None,
        "descripcion": descripcion or None,
        "enlace_oficial": enlace_oficial or None,
        "pdf_url": pdf_url or None,
    }

    try:
        db.session.execute(sql, params).first()
        db.session.commit()
        flash("Normativa creada correctamente.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error creando normativa")
        flash("No se pudo crear la normativa. Revisa los datos.", "danger")

    return redirect(url_for("normativa.list"))


@bp.post("/normativa/admin/delete", endpoint="admin_delete")
@login_required
def admin_delete():
    """
    Elimina una normativa por ID (solo admin). Usado por el botón 'Eliminar' en las tarjetas.
    """
    if current_user.role != Role.admin:
        abort(403)

    nid = (request.form.get("id") or "").strip()
    if not nid:
        flash("ID no proporcionado.", "warning")
        return redirect(url_for("normativa.list"))

    try:
        res = db.session.execute(
            text("DELETE FROM normativa WHERE id = :id RETURNING id"),
            {"id": nid}
        ).first()
        if res:
            db.session.commit()
            flash("Normativa eliminada.", "success")
        else:
            db.session.rollback()
            flash("No se encontró la normativa indicada.", "warning")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error eliminando normativa")
        flash("No se pudo eliminar la normativa.", "danger")

    return redirect(url_for("normativa.list"))
