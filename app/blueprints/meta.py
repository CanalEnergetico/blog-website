# app/blueprints/meta.py
from datetime import date, datetime, timedelta
from flask import Blueprint, Response, url_for, send_from_directory, current_app
from ..extensions import db
from ..models import Articulos
from ..utils import _parse_fecha

bp = Blueprint("meta", __name__)

@bp.get("/robots.txt")
def robots():
    return send_from_directory(current_app.static_folder, "robots.txt", mimetype="text/plain")

@bp.get("/sitemap.xml")
def sitemap():
    pages = []
    excluir = {"static", "robots", "sitemap", "news_sitemap"}
    for rule in current_app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0 and rule.endpoint.split(".")[-1] not in excluir:
            pages.append({
                "loc": url_for(rule.endpoint, _external=True),
                "lastmod": date.today().isoformat(),
                "changefreq": "weekly",
                "priority": "0.6",
            })
    posts = db.session.query(Articulos.slug, Articulos.fecha).all()
    for slug, f in posts:
        last = f if isinstance(f, date) else _parse_fecha(f) if f else date.today()
        pages.append({
            "loc": url_for("blog.detalle_articulo", slug=slug, _external=True),
            "lastmod": last.isoformat(),
            "changefreq": "weekly",
            "priority": "0.8",
        })
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
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

@bp.get("/news-sitemap.xml")
def news_sitemap():
    now = datetime.utcnow()
    cutoff = now - timedelta(days=2)

    posts = Articulos.query.order_by(Articulos.id.desc()).all()
    items = []
    for p in posts:
        d = p.fecha
        if not d:
            continue
        if not isinstance(d, datetime):
            # si guardas date o str, normaliza a datetime UTC del mediodía
            if isinstance(d, date):
                dt = datetime(d.year, d.month, d.day, 12, 0, 0)
            else:
                dd = _parse_fecha(d)
                dt = datetime(dd.year, dd.month, dd.day, 12, 0, 0)
        else:
            dt = d
        if dt >= cutoff:
            items.append({
                "loc": url_for("blog.detalle_articulo", slug=p.slug, _external=True),
                "date": dt,
                "title": p.titulo
            })

    if not items and posts:
        p = posts[0]
        dd = _parse_fecha(p.fecha) if p.fecha else now.date()
        dt = datetime(dd.year, dd.month, dd.day, 12, 0, 0)
        items.append({"loc": url_for("blog.detalle_articulo", slug=p.slug, _external=True), "date": dt, "title": p.titulo})

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
