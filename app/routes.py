# app/routes.py
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, send_from_directory, Response, current_app, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import Articulos, Comentarios, Tag
from .forms import PostForm, CommentForm
from .utils import generar_slug, _parse_fecha, parse_tags, tag_slug

bp = Blueprint("main", __name__)

# Inicio
@bp.route("/", endpoint="home")
def home():
    return render_template("index.html")

# Sobre nosotros
@bp.route("/sobre-nosotros", endpoint="sobre_nosotros")
def sobre_nosotros():
    return render_template("nosotros.html")

# Artículos
@bp.route("/articulos", endpoint="articulos_todos")
def articulos_todos():
    return render_template("articulos.html")

# Proximamente
@bp.route("/proximamente", endpoint="proximamente")
def proximamente():
    return render_template("proximamente.html")

# Detalle + comentarios
@bp.route("/articulos/<slug>", methods=["GET", "POST"], endpoint="detalle_articulo")
def detalle_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    form = CommentForm()
    if form.validate_on_submit():
        nuevo_comentario = Comentarios(
            articulo_id=post.id,
            nombre=form.nombre.data,
            correo=form.correo.data,
            comentario=form.comentario.data,
            fecha=date.today().strftime("%d/%m/%Y")
        )
        db.session.add(nuevo_comentario)
        db.session.commit()
        return redirect(url_for("main.detalle_articulo", slug=slug))
    comentarios = Comentarios.query.filter_by(articulo_id=post.id).order_by(Comentarios.id.desc()).all()
    return render_template("post.html", articulo=post, form=form, comentarios=comentarios)

# Helper para crear/obtener tag
def _get_or_create_tag(nombre: str) -> Tag:
    s = tag_slug(nombre)
    t = Tag.query.filter_by(slug=s).first()
    if t:
        return t
    t = Tag(nombre=nombre.strip(), slug=s)
    db.session.add(t)
    try:
        db.session.flush()  # consigue id sin commit completo
    except IntegrityError:
        db.session.rollback()
        t = Tag.query.filter_by(slug=s).first()
    return t

# Crear post
@bp.route("/new-post", methods=["GET", "POST"], endpoint="make_new_post")
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
            # legacy: guarda la primera por compat si quieres
            tag         = (nombres[0] if nombres else None),
            autor       = form.autor.data,
            contenido   = form.contenido.data,
            fecha       = date.today().strftime("%d/%m/%Y")
        )
        nuevo.tags = [_get_or_create_tag(n) for n in nombres]
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for('main.detalle_articulo', slug=nuevo.slug))
    return render_template('make-post.html', form=form)

# Editar
@bp.route("/edit-post/<slug>", methods=["GET", "POST"], endpoint="editar_articulo")
def editar_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    form = PostForm(
        titulo      = post.titulo,
        descripcion = post.descripcion,
        img_url     = post.img_url,
        img_fuente  = post.img_fuente,
        # pre-popula usando la relación nueva; si vacío, cae a legacy
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

        nombres = parse_tags(form.tags.data)
        post.tag = (nombres[0] if nombres else None)  # legacy opcional
        post.autor       = form.autor.data
        post.contenido   = form.contenido.data

        # Reemplaza asociaciones
        post.tags = [_get_or_create_tag(n) for n in nombres]

        db.session.commit()
        return redirect(url_for("main.detalle_articulo", slug=post.slug))
    return render_template("make-post.html", form=form, is_edit=True)

# Borrar post
@bp.route("/delete-post/<slug>", endpoint="delete_post")
def delete_post(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('main.articulos_todos'))

# Borrar comentario
@bp.route("/delete-comment/<int:id>", endpoint="delete_comment")
def delete_comment(id):
    comentario = Comentarios.query.get_or_404(id)
    db.session.delete(comentario)
    db.session.commit()
    return redirect(url_for('main.home'))

# Listar artículos por etiqueta
@bp.route("/tags/<tag_slug>", endpoint="articulos_por_tag")
def articulos_por_tag(tag_slug):
    tag = Tag.query.filter_by(slug=tag_slug).first_or_404()
    posts = (Articulos.query
             .join(Articulos.tags)
             .filter(Tag.id == tag.id)
             .order_by(Articulos.id.desc())
             .all())
    return render_template("articulos_por_tag.html", tag=tag, articulos=posts)

# Buscar por múltiples etiquetas: ?tags=python,flask&modo=and|or
@bp.route("/buscar-por-tags", endpoint="buscar_por_tags")
def buscar_por_tags():
    nombres = parse_tags(request.args.get("tags", ""))
    if not nombres:
        return redirect(url_for("main.articulos_todos"))
    slugs = [tag_slug(n) for n in nombres]
    modo = request.args.get("modo", "or").lower()

    q = Articulos.query.join(Articulos.tags).filter(Tag.slug.in_(slugs))
    if modo == "and":
        q = q.group_by(Articulos.id).having(func.count(func.distinct(Tag.id)) == len(slugs))

    posts = q.order_by(Articulos.id.desc()).all()
    return render_template("buscar_por_tags.html", tags=nombres, articulos=posts, modo=modo)

# robots.txt
@bp.route("/robots.txt", endpoint="robots")
def robots():
    from flask import current_app
    return send_from_directory(current_app.static_folder, "robots.txt", mimetype="text/plain")

# sitemap.xml
@bp.route("/sitemap.xml", methods=["GET"], endpoint="sitemap")
def sitemap():
    pages = []
    excluir = {"static", "robots", "sitemap"}
    for rule in current_app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0 and rule.endpoint not in excluir:
            pages.append({
                "loc": url_for(rule.endpoint, _external=True),
                "lastmod": date.today().isoformat(),
                "changefreq": "weekly",
                "priority": "0.6",
            })
    posts = db.session.query(Articulos.slug, Articulos.fecha).all()
    for slug, fecha_str in posts:
        last = _parse_fecha(fecha_str) if fecha_str else date.today()
        pages.append({
            "loc": url_for("main.detalle_articulo", slug=slug, _external=True),
            "lastmod": last.isoformat(),
            "changefreq": "weekly",
            "priority": "0.8",
        })

    # (Opcional) incluir páginas de tags:
    # for t in Tag.query.with_entities(Tag.slug).all():
    #     pages.append({
    #         "loc": url_for("main.articulos_por_tag", tag_slug=t.slug, _external=True),
    #         "lastmod": date.today().isoformat(),
    #         "changefreq": "weekly",
    #         "priority": "0.5",
    #     })

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for p in pages:
        xml += [
            "  <url>",
            f"    <loc>{p['loc']}</loc>",
            f"    <lastmod>{p['lastmod']}</lastmod>",
            f"    <changefreq>{p['changefreq']}</changefreq>",
            f"    <priority>{p['priority']}</priority>",
            "  </url>",
        ]
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")
