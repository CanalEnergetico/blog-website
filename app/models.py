# app/models.py
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from .extensions import db

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
    fecha:       Mapped[str]  = mapped_column(db.String(250), nullable=False)
    tag:         Mapped[Optional[str]] = mapped_column(db.String(50))

class Comentarios(db.Model):
    __tablename__ = "comentarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("articulos.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(db.String(100), nullable=False)
    correo: Mapped[str] = mapped_column(db.String(150), nullable=False)
    comentario: Mapped[str] = mapped_column(db.Text, nullable=False)
    fecha: Mapped[str] = mapped_column(db.String(250), nullable=False)

    articulo = db.relationship("Articulos", backref="comentarios")
