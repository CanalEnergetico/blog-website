# app/blueprints/comments.py
from flask import Blueprint, redirect, url_for, request, flash, abort
from flask_login import login_required
from ..extensions import db
from ..models import Comentarios
from ..security import can_manage_comment

bp = Blueprint("comments", __name__)

@bp.post("/comentarios/<int:cid>/edit", endpoint="edit_comment")
@login_required
def edit_comment(cid):
    c = Comentarios.query.get_or_404(cid)
    if not can_manage_comment(c):
        abort(403)
    texto = (request.form.get("comentario") or "").strip()
    if not texto:
        flash("El comentario no puede estar vacío.", "warning")
        return redirect(url_for("blog.detalle_articulo", slug=c.articulo.slug) + f"#c{c.id}")
    c.comentario = texto
    db.session.commit()
    flash("Comentario actualizado.", "success")
    return redirect(url_for("blog.detalle_articulo", slug=c.articulo.slug) + f"#c{c.id}")

@bp.post("/comentarios/<int:cid>/delete", endpoint="delete_comment")
@login_required
def delete_comment(cid):
    c = Comentarios.query.get_or_404(cid)
    if not can_manage_comment(c):
        abort(403)
    slug = c.articulo.slug
    db.session.delete(c)
    db.session.commit()
    flash("Comentario eliminado.", "info")
    return redirect(url_for("blog.detalle_articulo", slug=slug) + "#comentarios")
