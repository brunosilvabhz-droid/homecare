import logging
import smtplib
from email.message import EmailMessage
from app.core.config import settings
from app.core.security import create_email_token

logger=logging.getLogger(__name__)

def send_verification_email(user_id:str,email:str)->None:
    link=f"{settings.frontend_url.rstrip('/')}/confirmar-email?token={create_email_token(user_id)}"
    if not settings.smtp_host:
        logger.warning("SMTP não configurado. Link de confirmação para %s: %s",email,link)
        return
    message=EmailMessage()
    message["Subject"]="Confirme seu e-mail — Impacto Care"
    message["From"]=settings.smtp_from_email
    message["To"]=email
    message.set_content(f"Bem-vindo ao Impacto Care. Confirme seu e-mail acessando o link abaixo:\n\n{link}\n\nO link expira em {settings.email_verification_expire_hours} horas.")
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password or "")
        smtp.send_message(message)
