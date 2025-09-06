# app/routes.py
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, send_from_directory, Response, current_app, request, jsonify, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import re
from .extensions import db
from .models import Articulos, Comentarios, Tag, MercadoUltimo, MercadoDaily, User, Role
from .forms import PostForm, CommentForm
from .utils import generar_slug, _parse_fecha, parse_tags, tag_slug, pct_change_n, rolling_insert_30
# Importa las mismas funciones de siempre; tu app/markets.py está "disfrazada" para EIA
from .markets import td_price_batch, td_timeseries_daily, parse_last_ts

bp = Blueprint("main", __name__)

# --- Decorador simple por rol ---
def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.has_role(*roles):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def is_admin() -> bool:
    return current_user.is_authenticated and current_user.has_role('admin')

def can_manage_comment(c: Comentarios) -> bool:
    # dueño del comentario (por user_id o email) o admin
    if not current_user.is_authenticated:
        return False
    return is_admin() or (c.user_id == current_user.id) or (c.correo == current_user.email)

# --- Helpers para tokens de reset ---
def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

def gen_reset_token(email: str) -> str:
    return _reset_serializer().dumps(email, salt=current_app.config["PASSWORD_RESET_SALT"])

def verify_reset_token(token: str, max_age: int | None = None) -> str | None:
    if max_age is None:
        max_age = int(current_app.config.get("PASSWORD_RESET_EXP_SECS", 3600))  # 1h por defecto
    try:
        return _reset_serializer().loads(
            token,
            salt=current_app.config["PASSWORD_RESET_SALT"],
            max_age=max_age,
        )
    except (BadSignature, SignatureExpired):
        return None

# --- Política de contraseña: mínimo 8, solo letras o números ---
PASSWORD_REGEX = re.compile(r"^[A-Za-z0-9]{8,}$")
def valid_password(pw: str) -> bool:
    return bool(PASSWORD_REGEX.fullmatch(pw or ""))


# Inicio
@bp.route("/", endpoint="home")
def home():
    # 1) DESTACADO: último artículo etiquetado como "main"
    main_tag = Tag.query.filter((Tag.slug == "main") | (Tag.nombre.ilike("main"))).first()
    if main_tag:
        destacado = (
            Articulos.query
            .join(Articulos.tags)
            .filter(Tag.id == main_tag.id)
            .order_by(Articulos.id.desc())
            .first()
        )
    else:
        # Fallback legacy (mientras exista Articulos.tag)
        destacado = (
            Articulos.query
            .filter(Articulos.tag.ilike("main"))
            .order_by(Articulos.id.desc())
            .first()
        )

    # 2) Lista completa (más nuevo primero)
    ultimos = Articulos.query.order_by(Articulos.id.desc()).all()

    # 3) Fallback si no hay "main": usa el más reciente
    if destacado is None and ultimos:
        destacado = ultimos[0]

    # 4) Evita duplicados en tarjetas superiores
    otros = [a for a in ultimos if not destacado or a.id != destacado.id]

    return render_template("index.html", destacado=destacado, otros=otros)

# Sobre nosotros
@bp.route("/sobre-nosotros", endpoint="sobre_nosotros")
def sobre_nosotros():
    return render_template("nosotros.html")

# Artículos
@bp.route("/articulos", endpoint="articulos_todos")
def articulos_todos():
    page = request.args.get("page", 1, type=int)
    qtxt = (request.args.get("q") or "").strip()
    tag_param = (request.args.get("tag") or "").strip()

    q = Articulos.query

    # Filtro de texto
    if qtxt:
        like = f"%{qtxt}%"
        q = q.filter(or_(
            Articulos.titulo.ilike(like),
            Articulos.descripcion.ilike(like),
            Articulos.contenido.ilike(like),
            Articulos.tag.ilike(like),
        ))

    # Filtro por categoría principal
    if tag_param:
        q = q.filter(func.lower(func.btrim(Articulos.tag)) == tag_param.lower())

    # Orden + paginación
    q = q.order_by(Articulos.fecha.desc())
    pagination = db.paginate(q, page=page, per_page=12, error_out=False)

    # Opciones del desplegable
    tag_subq = (
        db.session.query(func.btrim(Articulos.tag).label("tag"))
        .filter(Articulos.tag.isnot(None), func.btrim(Articulos.tag) != "")
        .distinct()
        .subquery()
    )

    # Orden insensible a mayúsculas
    raw_tags = db.session.query(tag_subq.c.tag).order_by(func.lower(tag_subq.c.tag)).all()
    tags_main = [row[0] for row in raw_tags]  # lista de strings

    return render_template(
        "articulos.html",
        articulos=pagination.items,
        pagination=pagination,
        total=pagination.total,
        qtxt=qtxt,
        tag_sel=tag_param,
        tags_main=tags_main,
    )

# Próximamente
@bp.route("/proximamente", endpoint="proximamente")
def proximamente():
    return render_template("proximamente.html")

# Detalle + comentarios
@bp.route("/articulos/<slug>", methods=["GET", "POST"], endpoint="detalle_articulo")
def detalle_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()

    # POST: publicar comentario (solo usuarios logueados)
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Debes iniciar sesión para comentar.", "warning")
            return redirect(url_for("main.login"))

        texto = (request.form.get("comentario") or "").strip()
        if not texto:
            flash("Escribe un comentario.", "warning")
            return redirect(url_for("main.detalle_articulo", slug=slug) + "#comentarios")

        nuevo = Comentarios(
            articulo_id=post.id,
            user_id=current_user.id,
            nombre=current_user.nombre,
            correo=current_user.email,
            comentario=texto,
            fecha=date.today().strftime("%d/%m/%Y"),
        )
        db.session.add(nuevo)
        db.session.commit()
        flash("Comentario publicado.", "success")
        return redirect(url_for("main.detalle_articulo", slug=slug) + "#comentarios")

    # GET: render
    comentarios = Comentarios.query.filter_by(articulo_id=post.id)\
                                   .order_by(Comentarios.id.desc()).all()
    return render_template("post.html", articulo=post, comentarios=comentarios)

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
            # ⚠️ Articulos.fecha es db.Date -> guarda tipo date (no "dd/mm/YYYY")
            fecha       = date.today(),
        )
        nuevo.tags = [_get_or_create_tag(n) for n in nombres]
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for('main.detalle_articulo', slug=nuevo.slug))
    return render_template('make-post.html', form=form)


# Editar
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
        post.tag  = (nombres[0] if nombres else None)  # legacy opcional
        post.autor     = form.autor.data
        post.contenido = form.contenido.data
        post.tags      = [_get_or_create_tag(n) for n in nombres]

        db.session.commit()
        return redirect(url_for("main.detalle_articulo", slug=post.slug))
    return render_template("make-post.html", form=form, is_edit=True)


# Borrar post
@bp.route("/delete-post/<slug>", methods=["POST"], endpoint="delete_post")
@roles_required(Role.admin)
def delete_post(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('main.articulos_todos'))

#  Editar comentario
@bp.route("/comentarios/<int:cid>/edit", methods=["POST"], endpoint="edit_comment")
@login_required
def edit_comment(cid):
    c = Comentarios.query.get_or_404(cid)
    if not can_manage_comment(c):
        abort(403)
    texto = (request.form.get("comentario") or "").strip()
    if not texto:
        flash("El comentario no puede estar vacío.", "warning")
        return redirect(url_for("main.detalle_articulo", slug=c.articulo.slug) + f"#c{c.id}")
    c.comentario = texto
    db.session.commit()
    flash("Comentario actualizado.", "success")
    return redirect(url_for("main.detalle_articulo", slug=c.articulo.slug) + f"#c{c.id}")

# Borrar comentario
@bp.route("/comentarios/<int:cid>/delete", methods=["POST"], endpoint="delete_comment")
@login_required
def delete_comment(cid):
    c = Comentarios.query.get_or_404(cid)
    if not can_manage_comment(c):
        abort(403)
    slug = c.articulo.slug
    db.session.delete(c)
    db.session.commit()
    flash("Comentario eliminado.", "info")
    return redirect(url_for("main.detalle_articulo", slug=slug) + "#comentarios")

# Listar artículos por etiqueta
@bp.route("/tags/<tag_slug>", endpoint="articulos_por_tag")
def articulos_por_tag(tag_slug):
    tag = Tag.query.filter_by(slug=tag_slug).first_or_404()
    posts = (
        Articulos.query
        .join(Articulos.tags)
        .filter(Tag.id == tag.id)
        .order_by(Articulos.id.desc())
        .all()
    )
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

# sitemap para Google News
@bp.route("/news-sitemap.xml", methods=["GET"], endpoint="news_sitemap")
def news_sitemap():
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    cutoff = now - timedelta(days=2)

    posts = Articulos.query.order_by(Articulos.id.desc()).all()

    items = []
    for p in posts:
        d = _parse_fecha(p.fecha) if p.fecha else None
        if not d:
            continue
        dt = datetime(d.year, d.month, d.day, 12, 0, 0)
        if dt >= cutoff:
            items.append({
                "loc": url_for("main.detalle_articulo", slug=p.slug, _external=True),
                "date": dt,
                "title": p.titulo
            })

    # fallback: si no hay artículos recientes, mete el último
    if not items and posts:
        p = posts[0]
        d = _parse_fecha(p.fecha) if p.fecha else None
        dt = datetime(d.year, d.month, d.day, 12, 0, 0) if d else now
        items.append({
            "loc": url_for("main.detalle_articulo", slug=p.slug, _external=True),
            "date": dt,
            "title": p.titulo
        })

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
           'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">']

    for it in items:
        pub_date_iso = it["date"].strftime("%Y-%m-%dT%H:%M:%SZ")
        title = (it["title"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xml.append(f"""
  <url>
    <loc>{it["loc"]}</loc>
    <news:news>
      <news:publication>
        <news:name>Canal Energético</news:name>
        <news:language>es</news:language>
      </news:publication>
      <news:publication_date>{pub_date_iso}</news:publication_date>
      <news:title>{title}</news:title>
    </news:news>
  </url>""")

    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")

# ========= MERCADOS =========
@bp.route("/mercados", endpoint="mercados_home")
def mercados_home():
    return render_template("mercados.html")

@bp.route("/mercados/dashboard.json", endpoint="mercados_json")
def mercados_json():
    items = []
    unidades = {"brent": "USD/bbl", "wti": "USD/bbl"}
    nombres = {"brent": "Brent", "wti": "WTI"}
    for symbol in ("brent", "wti"):
        last = MercadoUltimo.query.filter_by(symbol=symbol).first()
        hist = (MercadoDaily.query
                .filter_by(symbol=symbol)
                .order_by(MercadoDaily.date.asc())
                .all())
        series = [h.close for h in hist]

        # <<< NUEVO: fechas para spark y fecha del último dato >>>
        dates = [
            h.date.isoformat() if hasattr(h.date, "isoformat") else str(h.date)
            for h in hist
        ]
        last_date = dates[-1] if dates else None
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

        items.append({
            "id": symbol,
            "name": nombres[symbol],
            "unit": unidades[symbol],
            "value": last.value if last else None,
            "asof": last.asof if last else None,
            "stale": bool(last.stale) if last else True,
            "chg_10d_pct": pct_change_n(series, 10),
            "chg_30d_pct": pct_change_n(series, 30),
            "spark": series[-30:],
            "spark_dates": dates[-30:],   # NUEVO
            "last_date": last_date,       # NUEVO
        })
    return jsonify({"updated_at": datetime.utcnow().isoformat()+"Z", "markets": items})

@bp.route("/tasks/refresh-mercados", methods=["POST"], endpoint="refresh_mercados")
def refresh_mercados():
    # Seguridad con token
    token = request.headers.get("X-Refresh-Token", "")
    if token != current_app.config.get("CANAL_KEY", ""):
        return {"error": "unauthorized"}, 401

    # Símbolos configurados (ahora RBRTE/RWTC para EIA)
    symmap = current_app.config.get("TWELVEDATA_SYMBOLS", {})
    brent_sym = symmap.get("brent")
    wti_sym   = symmap.get("wti")
    symbols_csv = ",".join([brent_sym, wti_sym])

    now_iso = datetime.utcnow().isoformat() + "Z"

    # 1) Último valor (usa td_price_batch "disfrazado" a EIA)
    try:
        prices = td_price_batch(symbols_csv)  # {"RBRTE":{"price":".."},"RWTC":{"price":".."}}
    except Exception as e:
        current_app.logger.exception("Error td_price_batch: %s", e)
        prices = {}

    for real_sym, logical in [(brent_sym, "brent"), (wti_sym, "wti")]:
        obj = prices.get(real_sym) or {}
        val = None
        try:
            if obj.get("price") is not None:
                val = float(obj.get("price"))
        except Exception:
            pass

        row = (MercadoUltimo.query.filter_by(symbol=logical).first()
               or MercadoUltimo(symbol=logical, unit="USD/bbl", value=0.0, asof=now_iso, stale=True))
        if val is not None:
            row.value, row.asof, row.stale = val, now_iso, False
        else:
            row.stale = True
            if not row.asof:
                row.asof = now_iso
        db.session.add(row)

    # 2) Historial (hasta 30 puntos) para el spark
    for logical, real_sym in [("brent", brent_sym), ("wti", wti_sym)]:
        try:
            ts = td_timeseries_daily(real_sym, outputsize=31)  # {"values":[{"datetime": "...","close": ...}, ...]}
            values = ts.get("values") or []
            # insertamos en orden ascendente para no romper la rotación
            for v in reversed(values[:30]):  # aseguramos máximo 30
                d = v.get("datetime", "")[:10]
                c = v.get("close")
                if d and (c is not None):
                    rolling_insert_30(db.session, logical, d, float(c), MercadoDaily)
        except Exception as e:
            current_app.logger.exception("Error time_series %s: %s", real_sym, e)

    db.session.commit()
    return {"ok": True}

# ========= USUARIOS =========
@bp.route("/registrarse", methods=["GET", "POST"])
def registrarse():
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not nombre or not email or not password:
            flash("Completa nombre, email y contraseña.", "warning")
            return redirect(url_for("main.registrarse"))
            # OJO: esta validación estricta en login hará que usuarios con contraseñas antiguas con símbolos no puedan entrar.
            # Si quieres permitir login de legacy y forzar nueva política solo en registro/reset, quita este bloque.

        if len(password) < 8 or not re.match(r"^[A-Za-z0-9]+$", password):
            flash("La contraseña debe tener al menos 8 caracteres y solo letras o números.", "warning")
            return redirect(url_for("main.login"))

        # Si el email está en la whitelist, será admin; si no, lector por defecto.
        admin_whitelist = current_app.config.get("ADMIN_EMAILS", [])
        role = Role.admin if email in admin_whitelist else Role.lector

        user = User(nombre=nombre, email=email, role=role)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ese email ya está registrado.", "danger")
            return redirect(url_for("main.registrarse"))

        flash("Cuenta creada correctamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("main.home"))

    # GET
    return render_template("auth/registrarse.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Credenciales inválidas.", "danger")
            return redirect(url_for("main.login"))

        login_user(user, remember=remember)
        next_url = request.args.get("next")
        flash("Has iniciado sesión.", "success")
        return redirect(next_url or url_for("main.home"))

    return render_template("auth/iniciar_sesion.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.home"))

# Política de Privacidad
@bp.get("/privacidad")
def privacy():
    return render_template("privacy.html")

# Olvidé mi contraseña
@bp.route("/forgot-password", methods=["GET", "POST"], endpoint="forgot_password")
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        # Genera y "envía" el enlace (por ahora, al log; luego lo mandas por SMTP)
        if user:
            token = gen_reset_token(user.email)
            reset_url = url_for("main.reset_password", token=token, _external=True)
            current_app.logger.info("Password reset link for %s: %s", email, reset_url)
        flash("Si el correo existe, te enviaremos instrucciones para restablecer la contraseña.", "info")
        return redirect(url_for("main.login"))
    return render_template("auth/forgot_password.html")

# Reset con token
@bp.route("/reset-password/<token>", methods=["GET", "POST"], endpoint="reset_password")
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("Enlace inválido o caducado.", "danger")
        return redirect(url_for("main.forgot_password"))

    user = User.query.filter_by(email=email).first_or_404()

    if request.method == "POST":
        new_pwd = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not valid_password(new_pwd):
            flash("La contraseña debe tener al menos 8 caracteres y solo letras o números.", "warning")
            return redirect(url_for("main.reset_password", token=token))

        if new_pwd != confirm:
            flash("Las contraseñas no coinciden.", "warning")
            return redirect(url_for("main.reset_password", token=token))

        user.set_password(new_pwd)   # tu método ya debe hashear+saltear
        db.session.commit()
        flash("Contraseña actualizada. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("main.login"))

    return render_template("auth/reset_password.html", email=email)
