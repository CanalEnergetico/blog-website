# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from flask_ckeditor import CKEditorField

class PostForm(FlaskForm):
    titulo      = StringField('Título', validators=[DataRequired()])
    descripcion = StringField('Descripción breve', validators=[DataRequired()])
    img_url     = StringField('URL de la imagen')
    img_fuente  = StringField('Fuente de la imagen')

    # NUEVO
    tags        = StringField('Etiquetas (separadas por comas)')

    autor       = StringField('Autor', validators=[DataRequired()])
    contenido   = CKEditorField('Contenido', validators=[DataRequired()])
    submit      = SubmitField('Publicar')

class CommentForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    correo = StringField('Correo electrónico', validators=[DataRequired()])
    comentario = StringField('Comentario', validators=[DataRequired()])
    submit = SubmitField('Enviar comentario')
