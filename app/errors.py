# app/errors.py
import logging
from flask import render_template, request
from .extensions import db

def init_error_handlers(app):
    log = logging.getLogger(__name__)

    @app.errorhandler(404)
    def not_found(e):
        log.warning("404: %s", request.path)
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        # evita transacciones colgadas
        db.session.rollback()
        log.exception("500 en %s", request.path)
        return render_template("errors/500.html"), 500
