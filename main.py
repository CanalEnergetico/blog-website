import os
# from flask_bootstrap import Bootstrap5 # Comentario Linea 3 error bootstrap
from flask import Flask, render_template, redirect, url_for,request, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm  import Mapped, mapped_column
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from flask_ckeditor import CKEditor, CKEditorField
from typing import Optional
from datetime import date,datetime, timedelta
from slugify import slugify
import pytz
import requests




app = Flask(__name__)

# Configuración de la base de datos
app.config["SECRET_KEY"] = os.environ.get("CANAL_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_CANAL_URI")    # solo local por ahora
db = SQLAlchemy(app)
ckeditor = CKEditor(app)

# Modelo de datos: tabla artículos
class Articulos(db.Model):
    __tablename__ = "articulos"
    id:          Mapped[int]  = mapped_column(primary_key=True)
    titulo:      Mapped[str]  = mapped_column(db.String(150), unique=True, nullable=False)
    slug:        Mapped[str]  = mapped_column(db.String(160), unique=True, nullable=False)
    descripcion: Mapped[str]  = mapped_column(db.String(300), nullable=False)
    img_url:     Mapped[Optional[str]] = mapped_column(db.String(300))
    img_fuente:  Mapped[Optional[str]] = mapped_column(db.String(300))
    contenido:   Mapped[str]  = mapped_column(db.Text, nullable=False)
    autor:       Mapped[str]  = mapped_column(db.String(300), nullable=False)
    fecha:       Mapped[str] = mapped_column(db.String(250), nullable=False)
    tag:         Mapped[Optional[str]] = mapped_column(db.String(50))

# Para el formulario
class PostForm(FlaskForm):
    titulo      = StringField('Título', validators=[DataRequired()])
    descripcion = StringField('Descripción breve', validators=[DataRequired()])
    img_url     = StringField('URL de la imagen')
    img_fuente  = StringField('Fuente de la imagen')
    tag         = StringField('Etiqueta principal')
    autor       = StringField('Autor', validators=[DataRequired()])
    contenido   = CKEditorField('Contenido', validators=[DataRequired()])
    submit      = SubmitField('Publicar')

# Crear la tabla por primera vez
with app.app_context():
    db.create_all()

# Esta función alimenta, por medio de una lista, los datos curiosos a todas las plantillas
@app.context_processor
def inject_datos_curiosos():
    datos_curiosos = [
        {
            "titulo": "Más del 75% de la electricidad de Panamá proviene de fuentes renovables.",
            "contenido": "Esto se debe principalmente a la hidroenergía, que históricamente ha representado la mayor parte de la generación eléctrica del país, seguida por la energía solar y eólica en crecimiento.",
            "fuente": "Secretaría Nacional de Energía de Panamá, Informe Energético Nacional 2022."
        },
        {
            "titulo": "Panamá fue el primer país de Centroamérica en tener una planta de gas natural licuado (GNL).",
            "contenido": "La planta de AES Colón, inaugurada en 2018, introdujo el GNL en la región con el objetivo de diversificar la matriz energética y mejorar la seguridad del suministro.",
            "fuente": "AES Panamá - aespanama.com"
        },
        {
            "titulo": "El Canal de Panamá genera su propia energía a través de plantas hidroeléctricas internas.",
            "contenido": "La Autoridad del Canal de Panamá opera las plantas de Gatún y Madden, que abastecen parte del consumo energético del propio canal y sus operaciones.",
            "fuente": "Autoridad del Canal de Panamá (ACP), Informe Anual 2023."
        },
        {
            "titulo": "Panamá importa el 100% de los combustibles fósiles que consume.",
            "contenido": "El país no cuenta con reservas propias de petróleo, gas o carbón, por lo que depende totalmente de las importaciones para suplir la demanda de derivados del petróleo, especialmente en el sector transporte.",
            "fuente": "Secretaría Nacional de Energía de Panamá, Balance Energético Nacional 2022."
        },
        {
            "titulo": "El sector transporte es el mayor consumidor de energía en Panamá.",
            "contenido": "Representa más del 40% del consumo energético final del país, superando ampliamente al sector residencial e industrial. Esta tendencia ha impulsado políticas públicas hacia la electromovilidad y la eficiencia en transporte público.",
            "fuente": "Secretaría Nacional de Energía de Panamá, Política Energética 2020–2050."
        },
        {
            "titulo": "Panamá tiene uno de los niveles más altos de electrificación en América Latina.",
            "contenido": "Cerca del 95% de la población panameña tiene acceso a electricidad, gracias a los esfuerzos de expansión de redes y proyectos de electrificación rural.",
            "fuente": "Banco Interamericano de Desarrollo (BID), Informe de Acceso Energético 2023."
        },
        {
            "titulo": "La energía solar ha crecido más de 10 veces en capacidad instalada desde 2015.",
            "contenido": "Gracias a políticas de incentivos y reducción de costos tecnológicos, Panamá ha incrementado considerablemente su capacidad solar, alcanzando más de 250 MW instalados en 2023.",
            "fuente": "ASEP Panamá, Estadísticas Energéticas 2023."
        },
        {
            "titulo": "Panamá busca ser un hub energético regional para Centroamérica y el Caribe.",
            "contenido": "Con su posición geográfica y la infraestructura del Canal, el país apuesta por convertirse en un centro de distribución de energías limpias, incluyendo hidrógeno verde y gas natural licuado.",
            "fuente": "Secretaría Nacional de Energía, Estrategia Nacional de Transición Energética 2020–2050."
        }
    ]
    return dict(datos_curiosos=datos_curiosos)

# Genera los slugs de los títulos de los artículos para los URLs
def generar_slug(titulo):
    base = slugify(titulo)
    slug = base
    n = 2
    while Articulos.query.filter_by(slug=slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


### RUTAS PRINCIPALES: WWW.CANALENERGETICO.COM ###
# Inicio
@app.route("/")
def home():
    articulos = Articulos.query.order_by(Articulos.fecha.desc()).all()
    return render_template("index.html", articulos=articulos)


# Variables globales para cachear precios con API
cache_precios = None
cache_timestamp = None
cache_duracion = timedelta(minutes=15)  # Refrescar cada 15 minutos


### API LLAMADA ###
@app.context_processor
def inject_precios():
    global cache_precios, cache_timestamp

    API_KEY = "9JHKJS3C9DDK76LK"
    simbolos = {
        "Brent": "BRENT",
        "WTI": "WTI",
        "Gas Natural": "NATURAL_GAS"
    }
    unidades = {
        "Brent": "USD/Bbl",
        "WTI": "USD/Bbl",
        "Gas Natural": "USD/MMBtu"
    }

    precios = {}
    ultima_actualizacion = None

    from datetime import datetime
    import pytz
    import requests

    # Si no hay cache o ya expiró
    if cache_precios is None or cache_timestamp is None or datetime.utcnow() - cache_timestamp > cache_duracion:
        try:
            for nombre, funcion in simbolos.items():
                response = requests.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": funcion,
                        "interval": "daily",
                        "apikey": API_KEY
                    },
                    timeout=10
                )
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    precio = data["data"][0]["value"]
                    precios[nombre] = {
                        "valor": round(float(precio), 2),
                        "unidad": unidades[nombre]
                    }
                    if ultima_actualizacion is None:
                        panama_tz = pytz.timezone("America/Panama")
                        ultima_actualizacion = datetime.now(panama_tz).strftime("%Y-%m-%d %H:%M")
                else:
                    precios[nombre] = {"valor": "No disponible", "unidad": unidades[nombre]}

            cache_precios = (precios, ultima_actualizacion)
            cache_timestamp = datetime.utcnow()

        except Exception as e:
            precios = {k: {"valor": f"Error: {str(e)}", "unidad": unidades[k]} for k in simbolos}
            ultima_actualizacion = None
            cache_precios = (precios, ultima_actualizacion)
            cache_timestamp = datetime.utcnow()

    else:
        precios, ultima_actualizacion = cache_precios

    return dict(precios=precios, ultima_actualizacion=ultima_actualizacion)


# Sobre nosotros
@app.route("/sobre-nosotros")
def sobre_nosotros():
    return render_template("nosotros.html")

# Artículos
@app.route("/articulos")
def articulos_todos():
    articulos = Articulos.query \
        .order_by(Articulos.fecha.desc()) \
        .all()
    return render_template("articulos.html", articulos=articulos)

# Detalle de un artículo
@app.route("/articulos/<slug>")
def detalle_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    return render_template("post.html", articulo=post)

# Formulario para crear un post
@app.route("/new-post", methods=["GET", "POST"])
def make_new_post():
    form = PostForm()
    if form.validate_on_submit():
        # Crear instancia del modelo
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
        return redirect(url_for('detalle_articulo', slug=nuevo.slug))
    return render_template('make-post.html', form=form)

# Formulario para editar un post
@app.route("/edit-post/<slug>", methods=["GET", "POST"])
def editar_articulo(slug):
    post = Articulos.query.filter_by(slug=slug).first_or_404()
    edit_form = PostForm(
        titulo=post.titulo,
        descripcion=post.descripcion,
        img_url=post.img_url,
        img_fuente=post.img_fuente,
        tag=post.tag,
        autor=post.autor,
        contenido=post.contenido,
    )
    if edit_form.validate_on_submit():
        if edit_form.titulo.data != post.titulo:
            post.slug = generar_slug(edit_form.titulo.data)
        # Crear instancia del modelo
        post.titulo     = edit_form.titulo.data
        post.descripcion= edit_form.descripcion.data
        post.img_url    = edit_form.img_url.data
        post.img_fuente = edit_form.img_fuente.data
        post.tag        = edit_form.tag.data
        post.autor      = edit_form.autor.data
        post.contenido  = edit_form.contenido.data
        db.session.commit()
        return redirect(url_for("detalle_articulo", slug=post.slug))
    return render_template("make-post.html", form=edit_form, is_edit=True)

# Borrar un post. CUIDADO: NO PREGUNTA DOS VECES!
@app.route("/delete-post/<slug>")
def delete_post(slug):
    post_to_delete = Articulos.query.filter_by(slug=slug).first_or_404()
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('articulos_todos'))

# Ejecutar en local
if __name__ == "__main__":
    app.run(debug=True, port=5002)
