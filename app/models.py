# app/models.py
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, Integer, ForeignKey, UniqueConstraint, Index, Date
from .extensions import db


# Tabla de asociación muchos-a-muchos
articulo_tags = Table(
    "articulo_tags",
    db.metadata,
    Column("articulo_id", Integer, ForeignKey("articulos.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("articulo_id", "tag_id", name="uq_articulo_tag")
)

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
    fecha:       Mapped[str]  = mapped_column(db.Date, nullable=False)

    # LEGACY (opcional, la puedes eliminar tras migrar):
    tag:         Mapped[Optional[str]] = mapped_column(db.String(50))

    # NUEVO: relación con Tag
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary=articulo_tags,
        back_populates="articulos",
        lazy="selectin"
    )

class Tag(db.Model):
    __tablename__ = "tags"
    id:     Mapped[int]  = mapped_column(primary_key=True)
    nombre: Mapped[str]  = mapped_column(db.String(50), nullable=False, unique=True)
    slug:   Mapped[str]  = mapped_column(db.String(60), nullable=False, unique=True)

    articulos: Mapped[list[Articulos]] = relationship(
        "Articulos",
        secondary=articulo_tags,
        back_populates="tags",
        lazy="selectin"
    )

# Índices útiles
Index("ix_tags_slug", Tag.slug, unique=True)
Index("ix_articulos_slug", Articulos.slug, unique=True)

class Comentarios(db.Model):
    __tablename__ = "comentarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("articulos.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(db.String(100), nullable=False)
    correo: Mapped[str] = mapped_column(db.String(150), nullable=False)
    comentario: Mapped[str] = mapped_column(db.Text, nullable=False)
    fecha: Mapped[str] = mapped_column(db.String(250), nullable=False)

    articulo = db.relationship("Articulos", backref="comentarios")

#Para las API de mercados
class MercadoUltimo(db.Model):
    __tablename__ = "mercado_ultimo"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False)  # 'brent' | 'wti'
    value  = db.Column(db.Float, nullable=False)
    unit   = db.Column(db.String(20), nullable=False)
    asof   = db.Column(db.String(40), nullable=False)  # ISO UTC
    stale  = db.Column(db.Boolean, nullable=False, default=False)

class MercadoDaily(db.Model):
    __tablename__ = "mercado_daily"

    id     = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)          # 'brent' | 'wti'
    date   = db.Column(db.String(10), nullable=False)          # 'YYYY-MM-DD'
    close  = db.Column(db.Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_symbol_date"),
    )
