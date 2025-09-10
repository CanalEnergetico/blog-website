# app/blueprints/blog.py
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Articulos, Comentarios, Tag, Role
from ..forms import PostForm
from ..utils import generar_slug, _parse_fecha, parse_tags, tag_slug
from ..security import roles_required

bp = Blueprint("blog", __name__)

# --- Listado con filtros y paginación ---
@bp.get("/articulos", endpoint="articulos_todos")
def articulos_todos():
    page = request.args.get("page", 1, type=int)
    qtxt = (request.args.get("q") or "").strip()
    tag_param = (request.args.get("tag") or "").strip()

    q = Articulos.query
    if qtxt:
        like = f"%{qtxt}%"
        q = q.filter(or_(
            Articulos.titulo.ilike(like),
            Articulos.descripcion.ilike(like),
            Articulos.contenido.ilike(like),
            Articulos.tag.ilike(like),
        ))

    if tag_param:
        q = q.filter(func.lower(func.btrim(Articulos.tag)) == tag_param.lower())

    q = q.order_by(Articulos.fecha.desc())
    pagination = db.paginate(q, page=page, per_page=12, error_out=False)

    tag_subq = (
        db.session.query(func.btrim(Articulos.tag).label("tag"))
        .filter(Articulos.tag.isnot(None), func.btrim(Articulos.tag) != "")
        .distinct()
        .subquery()
    )
    raw_tags = db.session.query(tag_subq.c.tag).order_by(func.lower(tag_subq.c.tag)).all()
    tags_main = [row[0] for row in raw_tags]

    return render_template(
        "articulos.html",
        articulos=pagination.items,
        pagination=pagination,
        total=pagination.total,
        qtxt=qtxt,
        tag_sel=tag_param,
        tags_main=tags_main,
    )

# --- Detalle + publicar comentario (requiere login) ---
@bp.route("/articulos/<slug>", methods=["GET", "POST"], endpoint="detalle_articulo")
def detalle_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Debes iniciar sesión para comentar.", "warning")
            return redirect(url_for("auth.login"))
        texto = (request.form.get("comentario") or "").strip()
        if not texto:
            flash("Escribe un comentario.", "warning")
            return redirect(url_for("blog.detalle_articulo", slug=slug) + "#comentarios")

        nuevo = Comentarios(
            articulo_id=post.id,
            user_id=getattr(current_user, "id", None),
            nombre=current_user.nombre,
            correo=current_user.email,
            comentario=texto,
            fecha=date.today().strftime("%d/%m/%Y"),
        )
        db.session.add(nuevo)
        db.session.commit()
        flash("Comentario publicado.", "success")
        return redirect(url_for("blog.detalle_articulo", slug=slug) + "#comentarios")

    comentarios = (Comentarios.query
                   .filter_by(articulo_id=post.id)
                   .order_by(Comentarios.id.desc()).all())
    return render_template("post.html", articulo=post, comentarios=comentarios)

# --- Helpers de tags (internos a este módulo) ---
def _get_or_create_tag(nombre: str) -> Tag:
    s = tag_slug(nombre)
    t = Tag.query.filter_by(slug=s).first()
    if t:
        return t
    t = Tag(nombre=nombre.strip(), slug=s)
    db.session.add(t)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        t = Tag.query.filter_by(slug=s).first()
    return t

# --- CRUD de posts ---
@bp.route("/new-post", methods=["GET", "POST"], endpoint="make_new_post")
@roles_required(Role.admin)
def make_new_post():
    form = PostForm()
    if form.validate_on_submit():
        nombres = parse_tags(form.tags.data)
        nuevo = Articulos(
            titulo      = form.titulo.data,
            slug        = generar_slug(form.titulo.data),
            descripcion = form.descripcion.data,
            img_url     = form.img_url.data,
            img_fuente  = form.img_fuente.data,
            tag         = (nombres[0] if nombres else None),  # legacy opcional
            autor       = form.autor.data,
            contenido   = form.contenido.data,
            # si tu modelo ya es date, guarda date; si es str, usa strftime
            fecha       = date.today(),  # ajusta si tu columna es string
        )
        nuevo.tags = [_get_or_create_tag(n) for n in nombres]
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for('blog.detalle_articulo', slug=nuevo.slug))
    return render_template('make-post.html', form=form)

@bp.route("/edit-post/<slug>", methods=["GET", "POST"], endpoint="editar_articulo")
@roles_required(Role.admin)
def editar_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    form = PostForm(
        titulo      = post.titulo,
        descripcion = post.descripcion,
        img_url     = post.img_url,
        img_fuente  = post.img_fuente,
        tags        = ", ".join([t.nombre for t in post.tags]) if post.tags else (post.tag or ""),
        autor       = post.autor,
        contenido   = post.contenido,
    )
    if form.validate_on_submit():
        if form.titulo.data != post.titulo:
            post.slug = generar_slug(form.titulo.data)

        post.titulo      = form.titulo.data
        post.descripcion = form.descripcion.data
        post.img_url     = form.img_url.data
        post.img_fuente  = form.img_fuente.data

        nombres   = parse_tags(form.tags.data)
        post.tag  = (nombres[0] if nombres else None)
        post.autor     = form.autor.data
        post.contenido = form.contenido.data
        post.tags      = [_get_or_create_tag(n) for n in nombres]

        db.session.commit()
        return redirect(url_for("blog.detalle_articulo", slug=post.slug))
    return render_template("make-post.html", form=form, is_edit=True)

@bp.post("/delete-post/<slug>", endpoint="delete_post")
@roles_required(Role.admin)
def delete_post(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('blog.articulos_todos'))

# --- Listar por tag ---
@bp.get("/tags/<tag_slug>", endpoint="articulos_por_tag")
def articulos_por_tag(tag_slug):
    tag = Tag.query.filter_by(slug=tag_slug).first_or_404()
    posts = (Articulos.query.join(Articulos.tags)
             .filter(Tag.id == tag.id)
             .order_by(Articulos.id.desc())
             .all())
    return render_template("articulos_por_tag.html", tag=tag, articulos=posts)

# --- Buscar por múltiples tags ---
@bp.get("/buscar-por-tags", endpoint="buscar_por_tags")
def buscar_por_tags():
    nombres = parse_tags(request.args.get("tags", ""))
    if not nombres:
        return redirect(url_for("blog.articulos_todos"))
    slugs = [tag_slug(n) for n in nombres]
    modo = request.args.get("modo", "or").lower()

    q = Articulos.query.join(Articulos.tags).filter(Tag.slug.in_(slugs))
    if modo == "and":
        q = q.group_by(Articulos.id).having(func.count(func.distinct(Tag.id)) == len(slugs))

    posts = q.order_by(Articulos.id.desc()).all()
    return render_template("buscar_por_tags.html", tags=nombres, articulos=posts, modo=modo)
