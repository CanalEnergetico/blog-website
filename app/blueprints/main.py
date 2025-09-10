# app/blueprints/main.py
from flask import Blueprint, render_template
from sqlalchemy import func
from ..models import Articulos, Tag

bp = Blueprint("main", __name__)

@bp.get("/", endpoint="home")
def home():
    main_tag = Tag.query.filter((Tag.slug == "main") | (Tag.nombre.ilike("main"))).first()
    if main_tag:
        destacado = (Articulos.query.join(Articulos.tags)
                     .filter(Tag.id == main_tag.id)
                     .order_by(Articulos.id.desc()).first())
    else:
        destacado = (Articulos.query
                     .filter(Articulos.tag.ilike("main"))
                     .order_by(Articulos.id.desc()).first())

    ultimos = Articulos.query.order_by(Articulos.id.desc()).all()
    if destacado is None and ultimos:
        destacado = ultimos[0]
    otros = [a for a in ultimos if not destacado or a.id != destacado.id]

    return render_template("index.html", destacado=destacado, otros=otros)

@bp.get("/sobre-nosotros", endpoint="sobre_nosotros")
def sobre_nosotros():
    return render_template("nosotros.html")

@bp.get("/proximamente", endpoint="proximamente")
def proximamente():
    return render_template("proximamente.html")
