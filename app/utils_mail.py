# app/utils_mail.py
import smtplib, ssl
from email.message import EmailMessage
from flask import current_app

def send_email(to_email: str, subject: str, html: str):
    """
    Envía un correo HTML usando la configuración de .env (Gmail con SMTP).
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config["MAIL_SENDER"]
    msg["To"] = to_email
    msg.set_content("Tu cliente de correo no soporta HTML.")
    msg.add_alternative(html, subtype="html")

    smtp_host = current_app.config["SMTP_HOST"]
    smtp_port = int(current_app.config["SMTP_PORT"])
    username = current_app.config["SMTP_USER"]
    password = current_app.config["SMTP_PASS"]

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(username, password)
        server.send_message(msg)
