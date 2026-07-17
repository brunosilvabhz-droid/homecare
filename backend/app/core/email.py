import logging
import smtplib
from email.message import EmailMessage
from app.core.config import settings
from app.core.security import create_email_token, create_password_reset_token

logger=logging.getLogger(__name__)

def send_relationship_email(email:str,subject:str,content:str,action_label:str|None=None,action_url:str|None=None)->bool:
    if not settings.smtp_host:
        logger.warning("SMTP não configurado. Automação '%s' destinada a %s",subject,email)
        return False
    message=EmailMessage();message["Subject"]=subject;message["From"]=settings.smtp_from_email;message["To"]=email
    body=content.strip()
    if action_label and action_url: body+=f"\n\n{action_label}:\n{action_url}"
    body+="\n\nImpacto Care — plataforma de gestão para atendimento domiciliar."
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password or "")
        smtp.send_message(message)
    return True

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

def send_password_reset_email(user_id:str,email:str)->None:
    link=f"{settings.frontend_url.rstrip('/')}/redefinir-senha?token={create_password_reset_token(user_id)}"
    if not settings.smtp_host:
        logger.warning("SMTP não configurado. Link de redefinição para %s: %s",email,link)
        return
    message=EmailMessage(); message["Subject"]="Redefina sua senha — Impacto Care"; message["From"]=settings.smtp_from_email; message["To"]=email
    message.set_content(f"Recebemos uma solicitação para redefinir sua senha. Acesse:\n\n{link}\n\nO link expira em 1 hora. Se não foi você, ignore esta mensagem.")
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password or "")
        smtp.send_message(message)

def send_support_ticket_email(ticket_number:str,category:str,description:str,user_name:str,user_email:str,organization_name:str)->bool:
    if not settings.smtp_host:
        logger.warning("SMTP não configurado. Chamado %s não enviado por e-mail",ticket_number)
        return False
    labels={"error":"Erro","question":"Dúvida","suggestion":"Sugestão","request":"Solicitação"}
    label=labels.get(category,category)
    message=EmailMessage()
    message["Subject"]=f"[Impacto Care] Chamado {ticket_number} — {label}"
    message["From"]=settings.smtp_from_email
    message["To"]=settings.support_email
    message["Reply-To"]=user_email
    message.set_content(f"Número do chamado: {ticket_number}\nTipo: {label}\nSolicitante: {user_name}\nE-mail: {user_email}\nConta: {organization_name}\n\nDescrição:\n{description}\n")
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password or "")
        smtp.send_message(message)
    return True

def send_plan_expiration_email(email:str,name:str,period_end:str,reminder_type:str,monthly_grace:bool)->bool:
    if not settings.smtp_host:
        logger.warning("SMTP não configurado. Lembrete de plano para %s não enviado",email)
        return False
    titles={"7_days":"Seu plano expira em 7 dias","1_day":"Seu plano expira amanhã","expired":"Seu período terminou","blocked":"Seu acesso ao plano expirou"}
    title=titles[reminder_type]
    if reminder_type=="expired" and monthly_grace: detail="O período terminou, mas seu plano mensal possui 5 dias de tolerância."
    elif reminder_type in {"expired","blocked"}: detail="O acesso aos recursos do plano fica bloqueado até uma nova contratação."
    else: detail=f"A vigência atual termina em {period_end}."
    link=f"{settings.frontend_url.rstrip('/')}/app/billing"
    message=EmailMessage();message["Subject"]=f"{title} — Impacto Care";message["From"]=settings.smtp_from_email;message["To"]=email
    message.set_content(f"Olá, {name}.\n\n{detail}\n\nEste é apenas um lembrete de expiração, não uma cobrança. Para continuar ou reativar o acesso, escolha um plano em:\n{link}\n\nImpacto Care")
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
        if settings.smtp_use_tls: smtp.starttls()
        if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password or "")
        smtp.send_message(message)
    return True

def send_visit_change_email(email:str,professional_name:str,patient_name:str,action:str,old_starts_at:str,new_starts_at:str|None=None)->bool:
    if not settings.smtp_host:
        logger.warning("SMTP não configurado. Alteração de agendamento de %s não enviada",patient_name)
        return False
    labels={"cancel":"cancelou","reschedule":"reagendou"}; label=labels[action]
    message=EmailMessage();message["Subject"]=f"Agendamento {label} — {patient_name}";message["From"]=settings.smtp_from_email;message["To"]=email
    detail=f"Horário anterior: {old_starts_at}."+(f"\nNovo horário: {new_starts_at}." if new_starts_at else "")
    message.set_content(f"Olá, {professional_name}.\n\n{patient_name} {label} o atendimento pelo link de confirmação.\n\n{detail}\n\nSua agenda no Impacto Care já foi atualizada.")
    try:
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
            if settings.smtp_use_tls: smtp.starttls()
            if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password or "")
            smtp.send_message(message)
        return True
    except Exception:
        logger.exception("Falha ao enviar alteração de agendamento para %s",email)
        return False
