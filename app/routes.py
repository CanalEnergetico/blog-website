# app/routes.py
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, send_from_directory, Response, current_app
from .extensions import db
from .models import Articulos, Comentarios
from .forms import PostForm, CommentForm
from .utils import generar_slug, _parse_fecha

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

# Crear post
@bp.route("/new-post", methods=["GET", "POST"], endpoint="make_new_post")
def make_new_post():
    form = PostForm()
    if form.validate_on_submit():
        nuevo = Articulos(
            titulo     = form.titulo.data,
            slug       = generar_slug(form.titulo.data),
            descripcion= form.descripcion.data,
            img_url    = form.img_url.data,
            img_fuente = form.img_fuente.data,
            tag        = form.tag.data,
            autor      = form.autor.data,
            contenido  = form.contenido.data,
            fecha      = date.today().strftime("%d/%m/%Y")
        )
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for('main.detalle_articulo', slug=nuevo.slug))
    return render_template('make-post.html', form=form)

# Editar
@bp.route("/edit-post/<slug>", methods=["GET", "POST"], endpoint="editar_articulo")
def editar_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    form = PostForm(
        titulo=post.titulo,
        descripcion=post.descripcion,
        img_url=post.img_url,
        img_fuente=post.img_fuente,
        tag=post.tag,
        autor=post.autor,
        contenido=post.contenido,
    )
    if form.validate_on_submit():
        if form.titulo.data != post.titulo:
            post.slug = generar_slug(form.titulo.data)
        post.titulo      = form.titulo.data
        post.descripcion = form.descripcion.data
        post.img_url     = form.img_url.data
        post.img_fuente  = form.img_fuente.data
        post.tag         = form.tag.data
        post.autor       = form.autor.data
        post.contenido   = form.contenido.data
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
    for rule in current_app.url_map.iter_rules():  # <— usa current_app
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
