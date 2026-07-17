import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, or_
from app.core.config import settings
from app.core.subscriptions import subscription_access
from app.core.whatsapp import configured, send_confirmation
from app.db.session import SessionLocal
from app.models import Visit, VisitStatus, Subscription, Plan, WhatsAppConfirmation

log=logging.getLogger("impactocare.automation");LOCAL_TZ=ZoneInfo("America/Sao_Paulo")
def confirmation_url(visit:Visit)->str:
    token=secrets.token_urlsafe(32);visit.confirmation_token_hash=hashlib.sha256(token.encode()).hexdigest();return f"{settings.frontend_url.rstrip('/')}/agendamento/{token}"
def run_once(now:datetime|None=None)->int:
    if not configured(): return 0
    now=now or datetime.now(timezone.utc);limit=now+timedelta(hours=24);sent=0
    with SessionLocal() as db:
        visits=db.scalars(
            select(Visit).where(
                Visit.status == VisitStatus.SCHEDULED,
                or_(Visit.patient_response.is_(None), Visit.patient_response != "confirmed"),
                Visit.starts_at > now,
                Visit.starts_at <= limit,
            ).order_by(Visit.starts_at)
        ).all()
        for visit in visits:
            subscription=db.scalar(select(Subscription).where(Subscription.organization_id==visit.organization_id));plan=db.get(Plan,subscription.plan_id) if subscription else None
            if not subscription or not plan or plan.code!="premium" or subscription_access(subscription)["blocked"] or plan.whatsapp_monthly_limit<=0 or not visit.patient.phone: continue
            delivery=db.scalar(select(WhatsAppConfirmation).where(WhatsAppConfirmation.visit_id==visit.id))
            if delivery and (delivery.status=="sent" or delivery.attempts>=3): continue
            month_start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            used=db.scalar(select(func.count()).select_from(WhatsAppConfirmation).where(WhatsAppConfirmation.organization_id==visit.organization_id,WhatsAppConfirmation.status=="sent",WhatsAppConfirmation.sent_at>=month_start)) or 0
            if used>=plan.whatsapp_monthly_limit: continue
            if not delivery: delivery=WhatsAppConfirmation(organization_id=visit.organization_id,visit_id=visit.id,status="pending",attempts=0);db.add(delivery)
            delivery.attempts=(delivery.attempts or 0)+1;url=confirmation_url(visit);starts_at=visit.starts_at.replace(tzinfo=timezone.utc) if visit.starts_at.tzinfo is None else visit.starts_at;local=starts_at.astimezone(LOCAL_TZ)
            try:
                delivery.provider_message_id=send_confirmation(visit.patient.phone,visit.patient.name,local.strftime("%d/%m/%Y"),local.strftime("%H:%M"),url);delivery.status="sent";delivery.sent_at=now;delivery.error_message=None;visit.confirmation_automatic_sent_at=now;sent+=1
            except Exception as error:
                delivery.status="failed";delivery.error_message=str(error)[:1000];log.exception("Falha no WhatsApp da visita %s",visit.id)
            db.commit()
    return sent
def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try: log.info("Confirmações enviadas: %s",run_once())
        except Exception: log.exception("Falha no ciclo de automação")
        time.sleep(max(settings.automation_interval_seconds,60))
if __name__=="__main__": main()
