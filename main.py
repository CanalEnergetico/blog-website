import os
#from flask_bootstrap import Bootstrap5 # Comentario Linea 3 error bootstrap
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from flask_ckeditor import CKEditor, CKEditorField
from datetime import datetime

app = Flask(__name__)

# Configuración de la base de datos
app.config["SECRET_KEY"] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///articulos.db"    # solo local por ahora
db = SQLAlchemy(app)
ckeditor = CKEditor(app)

# Modelo de datos: tabla artículos
class Articulos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), unique=True, nullable=False)
    descripcion = db.Column(db.String(300), nullable=False)
    img_url = db.Column(db.String(300), nullable=True)
    img_fuente = db.Column(db.String(300), nullable=True)  # ← Fuente de la imagen
    contenido = db.Column(db.Text, nullable=False)
    autor = db.Column(db.String(300), nullable=False)
    fecha = db.Column(db.String(60))
    tag = db.Column(db.String(50), nullable=True)  # ← Etiqueta

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

#  Me invento un par de artículos para probar
with app.app_context():
    art2 = Articulos(
        id=2,
        titulo="Colombia lidera ranking latinoamericano en eficiencia energética 2025",
        descripcion="Un informe internacional posiciona a Colombia como referente en ahorro energético en la región.",
        img_url="https://i.imgur.com/ABCEficienciaColombia.jpg",
        contenido="Según el más reciente informe del Energy Progress Index, Colombia ha logrado avances significativos en eficiencia energética...",
        autor="Rodrigo Pérez",
        fecha="2025-07-10"
    )
    db.session.add(art2)
    # db.session.commit()


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

### RUTAS PRINCIPALES ###
# Inicio
@app.route("/")
def home():
    articulos = Articulos.query.order_by(Articulos.fecha.desc()).all()
    return render_template("index.html", articulos=articulos)

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
@app.route("/articulos/<int:id>")
def detalle_articulo(id):
    articulo = Articulos.query.get_or_404(id)
    print(articulo.img_url)
    return render_template("post.html", articulo=articulo)

# Formulario para crear un post
@app.route('/new-post', methods=['GET', 'POST'])
def make_new_post():
    form = PostForm()
    if form.validate_on_submit():
        # Crear instancia del modelo
        nuevo = Articulos(
            titulo     = form.titulo.data,
            descripcion= form.descripcion.data,
            img_url    = form.img_url.data,
            img_fuente = form.img_fuente.data,
            tag        = form.tag.data,
            autor      = form.autor.data,
            contenido  = form.contenido.data,
            fecha      = datetime.utcnow().strftime('%Y-%m-%d')
        )
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for('detalle_articulo', id=nuevo.id))
    return render_template('make-post.html', form=form)


# Ejecutar en local
if __name__ == "__main__":
    app.run(debug=True, port=5002)