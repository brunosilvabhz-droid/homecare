import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.email import send_relationship_email
from app.core.config import settings
from app.core.subscriptions import subscription_access
from app.core.whatsapp import configured as whatsapp_configured, send_trial_expiration
from app.models import AIAnalysis, CommunicationAutomation, CommunicationLog, FinanceEntry, Patient, Role, ServiceRecord, Subscription, SubscriptionStatus, User, Visit

log=logging.getLogger("impactocare.relationship");LOCAL_TZ=ZoneInfo("America/Sao_Paulo")
TEMPLATES=(
 ("welcome","Bem-vindo à Impacto Care","confirmed",0,"Seu acesso está disponível","Olá, {{nome}}.\n\nComece completando seu perfil profissional e organize sua rotina em um só lugar.","/app/profile",False),
 ("first_patient","Cadastre seu primeiro paciente","no_patient",1,"Cadastre seu primeiro paciente","Olá, {{nome}}.\n\nO cadastro libera agenda, registros de atendimento e acompanhamento financeiro. Você também pode enviar um link de pré-cadastro à família.","/app/patients?new=1",False),
 ("first_schedule","Organize seu próximo atendimento","no_schedule",2,"Crie seu primeiro agendamento","Seu primeiro paciente já está cadastrado. Agora organize data, horário e duração do próximo atendimento.","/app/visits/new",False),
 ("first_record","Crie seu primeiro registro de atendimento","no_record",3,"Crie seu primeiro registro de atendimento","Após o atendimento, organize o resumo e as orientações autorizadas na linha do tempo.","/app/records?new=1",False),
 ("family_portal","Facilite o acompanhamento da família","family",5,"Conheça o Portal da Família","Compartilhe somente as informações que você autorizar com o responsável vinculado ao paciente.","/app/patients",False),
 ("finance","Você sabe quanto sua rotina está gerando?","finance",7,"Organize receitas e despesas","Acompanhe valores recebidos, pendentes, despesas e projeções financeiras.","/app/finance",False),
 ("ai","Prepare melhor seu próximo atendimento","ai",10,"Conheça o Assistente de IA","Use o histórico para revisar pontos importantes. A IA não diagnostica, não prescreve e todo conteúdo deve ser revisado pelo profissional.","/app/ai",False),
 ("progress_14","Veja o que você já organizou na Impacto Care","progress",14,"Continue sua configuração","Você já cadastrou {{pacientes}} paciente(s), criou {{agendamentos}} agendamento(s), {{registros}} registro(s) de atendimento e concluiu {{progresso}}% da configuração inicial.","/app",False),
 ("trial_day_20","Continue organizando sua rotina após o teste","remaining",10,"Conheça os planos disponíveis","Para continuar utilizando a plataforma após o teste, escolha o plano que melhor atende à sua rotina.","/app/billing",False),
 ("trial_7","Seu período gratuito termina em 7 dias","remaining",7,"Escolha um plano para continuar","Seu período gratuito termina em {{data_fim}}. Compare o Essencial e o Premium para manter o acesso.","/app/billing",False),
 ("trial_4","Economize escolhendo o plano anual","remaining",4,"Compare os ciclos mensal e anual","O plano anual possui menor valor mensal equivalente e é cobrado antecipadamente pelo período completo.","/app/billing",False),
 ("trial_2","Seu teste termina em 2 dias","remaining",2,"Evite a interrupção do acesso","Seu período gratuito termina em {{data_fim}}. Seus dados seguem as regras de retenção previstas nos termos.","/app/billing",False),
 ("trial_1","Amanhã termina seu período gratuito","remaining",1,"Escolha um plano para manter o acesso","Escolha o plano Essencial ou Premium para continuar organizando sua rotina.","/app/billing",False),
 ("trial_0","Hoje é o último dia do seu teste","remaining",0,"Continue com a Impacto Care","Hoje termina seu período gratuito. Se a plataforma ajuda sua rotina, escolha um plano para continuar.","/app/billing",False),
 ("trial_expired","Seu período gratuito foi encerrado","remaining",-1,"Reative sua conta","Para voltar a utilizar as funcionalidades, selecione um plano e conclua a contratação.","/app/billing",False),
 ("trial_expired_3","Ainda quer organizar sua rotina com a Impacto Care?","remaining",-3,"Reative sua conta","Você pode reativar sua conta e continuar utilizando a plataforma escolhendo um plano.","/app/billing",False),
 ("inactivity","Continue de onde parou","inactive",7,"Sua configuração inicial ainda não foi concluída","Seu período gratuito continua disponível. Retorne à plataforma e continue pela próxima etapa pendente.","/app",False),
)
def ensure_templates(db:Session)->dict[str,CommunicationAutomation]:
    rows={x.code:x for x in db.scalars(select(CommunicationAutomation)).all()}
    for code,name,trigger,offset,subject,content,path,promo in TEMPLATES:
        if code not in rows:
            item=CommunicationAutomation(code=code,name=name,channel="email",trigger_type=trigger,offset_days=offset,subject=subject,content=content,action_path=path,is_active=True,promotional=promo);db.add(item);db.flush();rows[code]=item
    return rows
def counts(db:Session,user:User)->dict:
    org=user.organization_id
    return {"patients":db.scalar(select(func.count()).select_from(Patient).where(Patient.organization_id==org)) or 0,"visits":db.scalar(select(func.count()).select_from(Visit).where(Visit.organization_id==org)) or 0,"records":db.scalar(select(func.count()).select_from(ServiceRecord).where(ServiceRecord.organization_id==org)) or 0,"finance":db.scalar(select(func.count()).select_from(FinanceEntry).where(FinanceEntry.organization_id==org)) or 0,"ai":db.scalar(select(func.count()).select_from(AIAnalysis).where(AIAnalysis.organization_id==org)) or 0}
def eligible(item:CommunicationAutomation,user:User,subscription:Subscription,metrics:dict,now:datetime)->bool:
    if not user.is_active or not user.email_verified_at or not user.email_operational:return False
    access=subscription_access(subscription,now.date());paid=subscription.status==SubscriptionStatus.ACTIVE
    if item.promotional and (not user.email_marketing or paid):return False
    if item.trigger_type=="confirmed":return True
    age=(now.date()-user.email_verified_at.date()).days
    if item.trigger_type=="no_patient":return age>=item.offset_days and metrics["patients"]==0 and not access["blocked"]
    if item.trigger_type=="no_schedule":return age>=item.offset_days and metrics["patients"]>0 and metrics["visits"]==0 and not access["blocked"]
    if item.trigger_type=="no_record":return age>=item.offset_days and metrics["visits"]>0 and metrics["records"]==0 and not access["blocked"]
    if item.trigger_type=="family":return age>=item.offset_days and not access["blocked"]
    if item.trigger_type=="finance":return age>=item.offset_days and metrics["finance"]==0 and not access["blocked"]
    if item.trigger_type=="ai":return age>=item.offset_days and metrics["ai"]==0 and not access["blocked"]
    if item.trigger_type=="progress":return age>=item.offset_days and not access["blocked"]
    if item.trigger_type=="inactive":return subscription.status==SubscriptionStatus.TRIAL and user.last_login_at is not None and (now.date()-user.last_login_at.date()).days>=item.offset_days
    if item.trigger_type=="remaining":return subscription.status==SubscriptionStatus.TRIAL and subscription.current_period_end is not None and (subscription.current_period_end-now.date()).days==item.offset_days
    return False
def run_once(now:datetime|None=None)->int:
    from app.db.session import SessionLocal
    now=now or datetime.now(timezone.utc);local=now.astimezone(LOCAL_TZ)
    if not time(8)<=local.time()<time(18):return 0
    sent=0
    with SessionLocal() as db:
        templates=ensure_templates(db);users=db.scalars(select(User).where(User.role==Role.PROFESSIONAL,User.is_active.is_(True))).all()
        for user in users:
            subscription=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id))
            if not subscription:continue
            metrics=counts(db,user)
            for item in templates.values():
                key=f"{user.id}:{subscription.id}:{item.code}:email"
                entry=db.scalar(select(CommunicationLog).where(CommunicationLog.idempotency_key==key))
                if entry and (entry.status=="sent" or entry.attempts>=3):continue
                if not item.is_active or not eligible(item,user,subscription,metrics,now):continue
                if not entry:
                    entry=CommunicationLog(organization_id=user.organization_id,user_id=user.id,automation_id=item.id,channel="email",template_code=item.code,idempotency_key=key,scheduled_at=now,status="processing",attempts=0);db.add(entry)
                entry.status="processing";entry.attempts+=1;entry.attempted_at=now;db.flush();content=item.content.replace("{{nome}}",user.name.split()[0]).replace("{{data_fim}}",subscription.current_period_end.strftime("%d/%m/%Y") if subscription.current_period_end else "").replace("{{pacientes}}",str(metrics["patients"])).replace("{{agendamentos}}",str(metrics["visits"])).replace("{{registros}}",str(metrics["records"]));content=content.replace("{{progresso}}",str(min(100,sum(1 for value in (metrics["patients"],metrics["visits"],metrics["records"],metrics["finance"],metrics["ai"]) if value)*20)))
                try:
                    ok=send_relationship_email(user.email,item.subject or item.name,content,item.name,f"{settings.frontend_url.rstrip('/')}{item.action_path or '/app'}");entry.status="sent" if ok else "failed";entry.sent_at=now if ok else None;entry.error_message=None if ok else "SMTP não configurado";sent+=int(ok)
                except Exception as error:entry.status="failed";entry.error_message=str(error)[:1000];log.exception("Falha na automação %s",item.code)
                db.commit()
            remaining=(subscription.current_period_end-now.date()).days if subscription.current_period_end else None
            if remaining==7 and user.whatsapp_allowed and user.phone and whatsapp_configured() and local.time()>=time(9):
                key=f"{user.id}:{subscription.id}:trial_7:whatsapp";entry=db.scalar(select(CommunicationLog).where(CommunicationLog.idempotency_key==key))
                if not entry:
                    entry=CommunicationLog(organization_id=user.organization_id,user_id=user.id,channel="whatsapp",template_code="trial_7",idempotency_key=key,scheduled_at=now,status="processing",attempts=1,attempted_at=now);db.add(entry)
                    try:entry.provider_id=send_trial_expiration(user.phone,user.name.split()[0],f"{settings.frontend_url.rstrip('/')}/app/billing");entry.status="sent";entry.sent_at=now;sent+=1
                    except Exception as error:entry.status="failed";entry.error_message=str(error)[:1000];log.exception("Falha no WhatsApp de conversão")
                    db.commit()
        db.commit()
    return sent
