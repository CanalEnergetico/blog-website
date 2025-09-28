# app/blueprints/auth.py
from datetime import datetime
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import User, Role
from ..security import valid_password
from ..auth_tokens import gen_reset_token, verify_reset_token, gen_email_token, verify_email_token
from ..utils_mail import send_email

bp = Blueprint("auth", __name__)

# --- Helpers de correo (anti-placeholder) ---
_BAD_DOMAINS = {"example.com", "ejemplo.com", "example.org", "test.com"}

def _resolve_contact_to() -> str:
    """
    Devuelve el destinatario para pruebas/avisos.
    Prioriza env CONTACT_TO, luego config CONTACT_TO, y finalmente un fallback seguro.
    """
    to = (os.getenv("CONTACT_TO") or current_app.config.get("CONTACT_TO") or "").strip()
    return to or "info.canalenergetico@gmail.com"

def _is_bad_domain(addr: str) -> bool:
    try:
        dom = addr.split("@", 1)[1].lower()
        return dom in _BAD_DOMAINS
    except Exception:
        return True  # considera inválido si no se puede parsear


@bp.route("/registrarse", methods=["GET", "POST"])
def registrarse():
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not nombre or not email or not password:
            flash("Completa nombre, email y contraseña.", "warning")
            return render_template("auth/registrarse.html", nombre=nombre, email=email)
        if not valid_password(password):
            flash("La contraseña debe tener al menos 8 caracteres.", "warning")
            return render_template("auth/registrarse.html", nombre=nombre, email=email)

        admin_whitelist = current_app.config.get("ADMIN_EMAILS", [])
        role = Role.admin if email in admin_whitelist else Role.lector

        user = User(nombre=nombre, email=email, role=role)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ese email ya está registrado.", "danger")
            return render_template("auth/registrarse.html", nombre=nombre, email=email)

        try:
            token = gen_email_token(user.email)
            verify_url = url_for("auth.verify_email", token=token, _external=True)
            html = f"""
            <h2>Verifica tu correo</h2>
            <p>Hola {user.nombre}, gracias por registrarte en Canal Energético.</p>
            <p>Haz clic para verificar tu cuenta (48 horas):</p>
            <p><a href="{verify_url}">{verify_url}</a></p>
            """
            send_email(
                to_email=user.email,
                subject="Verifica tu correo – Canal Energético",
                html=html,
                            )
            flash("¡Cuenta registrada correctamente! Revisa tu correo para verificar la cuenta.", "success")
            if current_app.debug:
                flash(f"Enlace de verificación (solo dev): {verify_url}", "secondary")
        except Exception as e:
            current_app.logger.exception("No se pudo enviar verificación: %s", e)
            flash("¡Cuenta registrada correctamente! Luego podrás verificar tu correo para tener acceso a todas las funcionalidades de la web.", "info")

        return redirect(url_for("auth.login"))
    return render_template("auth/registrarse.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Credenciales inválidas.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user, remember=remember)
        next_url = request.args.get("next")
        flash("Has iniciado sesión.", "success")
        return redirect(next_url or url_for("main.home"))
    return render_template("auth/iniciar_sesion.html")


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.home"))


@bp.get("/privacidad")
def privacy():
    return render_template("privacy.html")


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if email:
            user = User.query.filter_by(email=email).first()
            if user:
                token = gen_reset_token(user.email)
                reset_url = url_for("auth.reset_password", token=token, _external=True)
                html = f"""
                <h2>Restablecer contraseña</h2>
                <p>Hola {user.nombre}, haz clic para restablecer tu contraseña (2 h):</p>
                <p><a href="{reset_url}">{reset_url}</a></p>
                """
                try:
                    send_email(user.email, "Restablecer contraseña – Canal Energético", html)
                except Exception:
                    current_app.logger.exception("No se pudo enviar reset password")
        flash("Si el correo existe, te enviaremos instrucciones.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("Enlace inválido o caducado.", "warning")
        return redirect(url_for("auth.forgot_password"))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_pwd = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if new_pwd != confirm:
            flash("Las contraseñas no coinciden.", "warning")
            return redirect(url_for("auth.reset_password", token=token))
        if not valid_password(new_pwd):
            flash("La contraseña debe tener al menos 8 caracteres.", "warning")
            return redirect(url_for("auth.reset_password", token=token))
        user.set_password(new_pwd)
        db.session.commit()
        flash("Contraseña actualizada. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", token=token, email=email)


@bp.get("/verify-email/<token>")
def verify_email(token):
    email = verify_email_token(token)
    if not email:
        flash("Enlace inválido o caducado. Solicita un reenvío.", "warning")
        return redirect(url_for("auth.login"))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for("auth.login"))
    if user.verified_at:
        flash("Tu correo ya estaba verificado.", "info")
        return redirect(url_for("main.home"))
    user.verified_at = datetime.utcnow()
    db.session.commit()
    flash("¡Email verificado!", "success")
    return redirect(url_for("main.home"))


@bp.post("/resend-verification")
@login_required
def resend_verification():
    if current_user.verified_at:
        flash("Tu correo ya está verificado.", "info")
        return redirect(url_for("main.home"))
    token = gen_email_token(current_user.email)
    verify_url = url_for("auth.verify_email", token=token, _external=True)
    html = f"""
    <h2>Verifica tu correo</h2>
    <p>Hola {current_user.nombre}, este es tu nuevo enlace (48 h):</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    """
    try:
        send_email(current_user.email, "Reenviar verificación – Canal Energético", html)
        flash("Te reenviamos el correo de verificación.", "info")
    except Exception:
        current_app.logger.exception("No se pudo reenviar verificación")
        flash("No pudimos reenviar ahora. Intenta más tarde.", "warning")
    return redirect(url_for("main.home"))


@bp.get("/test-mail")
def test_mail():
    """
    Ruta de prueba de SMTP.
    """
    to_addr = _resolve_contact_to()
    if _is_bad_domain(to_addr):
        current_app.logger.warning("Bloqueado envío a dominio de ejemplo: %s", to_addr)
        return "Destinatario inválido para test (dominio de ejemplo). Configura CONTACT_TO.", 400

    send_email(
        to_email=to_addr,
        subject="Prueba Blog Energético",
        html="<h1>Funciona!</h1><p>Este es un test de SMTP.</p>",
    )
    return f"Correo de prueba enviado a {to_addr}"
