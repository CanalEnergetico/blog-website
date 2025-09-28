# app/models.py
from enum import Enum
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, Integer, ForeignKey, UniqueConstraint, Index, Date
from .extensions import db

# Tabla de asociación muchos-a-muchos
articulo_tags = Table(
    "articulo_tags", db.metadata,
    Column("articulo_id", Integer, ForeignKey("articulos.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("articulo_id", "tag_id", name="uq_articulo_tag")
)

# ARTÍCULOS
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

    # helper no persistente
    @property
    def tag_principal(self) -> str | None:
        # prioriza legacy .tag; si no, toma el 1º de .tags
        if self.tag:
            return self.tag
        return self.tags[0].nombre if self.tags else None

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
    user_id: Mapped[int | None] = mapped_column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # NUEVO
    nombre: Mapped[str] = mapped_column(db.String(100), nullable=False)
    correo: Mapped[str] = mapped_column(db.String(150), nullable=False)
    comentario: Mapped[str] = mapped_column(db.Text, nullable=False)
    fecha: Mapped[str] = mapped_column(db.String(250), nullable=False)

    articulo = db.relationship("Articulos", backref="comentarios")
    usuario = db.relationship("User", backref="comentarios", lazy="joined")  # opcional

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

# USUARIOS
class Role(Enum):
    admin = "admin"
    colaborador = "colaborador"
    lector = "lector"

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id:            Mapped[int] = mapped_column(primary_key=True)
    nombre:        Mapped[str] = mapped_column(db.String(120), nullable=False)
    email:         Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True, default=None)


    role: Mapped[Role] = mapped_column(db.Enum(Role, name="role_enum"), nullable=False, default=Role.lector)

    # Estado y trazas
    is_active: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Helpers de contraseña y autorización ---
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles) -> bool:
        """
        Permite: user.has_role('admin','colaborador') o user.has_role(Role.admin)
        """
        own = self.role.value
        wanted = [(r.value if isinstance(r, Role) else str(r)) for r in roles]
        return own in wanted

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None

#Tabla para "Ultimo comentario mercados"
class SiteNote(db.Model):
    __tablename__ = "site_notes"
    # “singleton” por clave
    key = db.Column(db.String(64), primary_key=True)
    content = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )
    author_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{User.__tablename__}.id"),  # típicamente "users.id"
        nullable=True,
        index=True,
    )
    author = db.relationship("User", lazy="joined")