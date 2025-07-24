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

# Configuracion de la base de datos
app.config["SECRET_KEY"] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///articulos.db"    # solo local por ahora
db = SQLAlchemy(app)
ckeditor = CKEditor(app)

# Modelo de datos: tabla articulos
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

#  Me invento un par de articulos para probar
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

# Rutas principales
@app.route("/")
def home():
    articulos = Articulos.query.order_by(Articulos.fecha.desc()).all()
    return render_template("index.html", articulos=articulos)

# Pagina de sobre nosotros
@app.route("/sobre-nosotros")
def sobre_nosotros():
    return render_template("nosotros.html")

# Todos los articulos
@app.route("/articulos")
def articulos_todos():
    articulos = Articulos.query \
        .order_by(Articulos.fecha.desc()) \
        .all()

    return render_template("articulos.html", articulos=articulos)

# Detalle de un articulo
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