from datetime import date, datetime, timezone, time, timedelta
import base64, binascii, hashlib, secrets, io, html
import json
import logging
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from zoneinfo import ZoneInfo
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from app.db.session import get_db
from app.deps import current_user, professional, account_professional, admin
from app.core.security import hash_password, verify_password, create_token, decode_email_token, decode_password_reset_token
from app.core.email import send_verification_email, send_password_reset_email, send_support_ticket_email, send_visit_change_email
from app.core.routing import geocode, calculate_route, money
from app.core.config import settings
from app.core.captcha import verify_turnstile
from app.core.billing import create_asaas_checkout, cancel_asaas_subscription
from app.core.subscriptions import subscription_access
from app.core.ai import generate_analysis
from app.models import Organization, User, GoogleIdentity, Role, Patient, Responsible, Visit, ServiceRecord, FinanceEntry, SupportTicket, AuditLog, VisitStatus, Plan, Subscription, SubscriptionStatus, BillingCycle, Vehicle, IntakeRequest, BillingWebhookEvent, ProfessionalAvailability, SystemSetting, AIAnalysis, WhatsAppConfirmation, ProductEvent, CommunicationAutomation, CommunicationLog, ContextMessageInteraction, ExitSurveyResponse
from app.relationship_automation import ensure_templates
from app.onboarding import event as product_event, status as onboarding_status
from app.schemas import *
router=APIRouter()
ADMIN_SETTINGS_KEY="platform"
def platform_settings(db:Session)->AdminSettings:
    item=db.scalar(select(SystemSetting).where(SystemSetting.key==ADMIN_SETTINGS_KEY))
    return AdminSettings.model_validate(item.value if item else {})
def audit(db,user,action,resource): db.add(AuditLog(organization_id=user.organization_id,user_id=user.id,action=action,resource=resource))
def owned(db,model,id,user):
    item=db.scalar(select(model).where(model.id==id,model.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Recurso não encontrado")
    return item
LOCAL_TZ=ZoneInfo("America/Sao_Paulo")
def visit_by_token(db:Session,token:str):
    item=db.scalar(select(Visit).where(Visit.confirmation_token_hash==hashlib.sha256(token.encode()).hexdigest()))
    if not item: raise HTTPException(404,"Link de agendamento inválido")
    return item
def ensure_confirmation_url(db:Session,item:Visit)->str:
    token=secrets.token_urlsafe(32);item.confirmation_token_hash=hashlib.sha256(token.encode()).hexdigest()
    return f"{settings.frontend_url.rstrip('/')}/agendamento/{token}"
def ai_limit(db:Session,user:User)->tuple[int,int]:
    subscription=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id));plan=db.get(Plan,subscription.plan_id) if subscription else None
    limit=5 if subscription and subscription.status==SubscriptionStatus.TRIAL else (plan.ai_daily_limit if plan else 0)
    local_now=datetime.now(LOCAL_TZ);start=local_now.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc);end=start+timedelta(days=1)
    used=db.scalar(select(func.count()).select_from(AIAnalysis).where(AIAnalysis.organization_id==user.organization_id,AIAnalysis.created_at>=start,AIAnalysis.created_at<end)) or 0
    return limit,used
def slot_is_available(db:Session,visit:Visit,starts_at:datetime,duration:int)->bool:
    local=starts_at.astimezone(LOCAL_TZ); end=local+timedelta(minutes=duration)
    windows=db.scalars(select(ProfessionalAvailability).where(ProfessionalAvailability.professional_id==visit.professional_id,ProfessionalAvailability.weekday==local.weekday(),ProfessionalAvailability.is_active.is_(True))).all()
    if not any(local.time()>=w.start_time and end.time()<=w.end_time and local.date()==end.date() for w in windows): return False
    utc_start=local.astimezone(timezone.utc);utc_end=end.astimezone(timezone.utc)
    conflicts=db.scalars(select(Visit).where(Visit.professional_id==visit.professional_id,Visit.id!=visit.id,Visit.status!=VisitStatus.CANCELED,Visit.starts_at<utc_end)).all()
    return not any((other.starts_at+timedelta(minutes=other.duration_minutes))>utc_start for other in conflicts)
def sync_patient_finance(db:Session,patient:Patient):
    db.query(FinanceEntry).filter(FinanceEntry.organization_id==patient.organization_id,FinanceEntry.patient_id==patient.id,FinanceEntry.source=="patient_sessions",FinanceEntry.paid.is_(False)).delete()
    paid=db.scalar(select(func.count()).select_from(FinanceEntry).where(FinanceEntry.patient_id==patient.id,FinanceEntry.source=="patient_sessions",FinanceEntry.paid.is_(True))) or 0
    if patient.session_value and patient.session_count:
        for index in range(paid,patient.session_count):
            db.add(FinanceEntry(organization_id=patient.organization_id,patient_id=patient.id,entry_type="income",source="patient_sessions",description=f"Sessão {index+1}/{patient.session_count} — {patient.name}",amount=patient.session_value,due_date=datetime.now(timezone.utc).date()+timedelta(days=index*7),paid=False))
@router.get("/auth/config")
def auth_config(db:Session=Depends(get_db)):
    operational=platform_settings(db)
    return {"google_client_id":settings.google_oauth_client_id if operational.google_login_enabled else None,"google_enabled":bool(settings.google_oauth_client_id and operational.google_login_enabled)}
@router.post("/auth/register",response_model=Message,status_code=201)
def register(data:Register,db:Session=Depends(get_db)):
    operational=platform_settings(db)
    if not operational.registration_enabled or operational.maintenance_mode: raise HTTPException(503,operational.maintenance_message if operational.maintenance_mode else "Novos cadastros estão temporariamente suspensos")
    if not data.accept_lgpd: raise HTTPException(422,"É necessário aceitar o consentimento de privacidade")
    if db.scalar(select(User).where(User.email==data.email.lower())): raise HTTPException(409,"E-mail já cadastrado")
    org=Organization(name=data.organization_name); db.add(org); db.flush()
    profile=data.model_dump(exclude={"organization_name","password","accept_lgpd"})
    profile["email"]=str(data.email).lower(); profile["state"]=data.state.upper()
    if profile.get("council_state"): profile["council_state"]=profile["council_state"].upper()
    user=User(**profile,password_hash=hash_password(data.password),role=Role.PROFESSIONAL,organization_id=org.id,registration_source="password")
    db.add(user); plan=db.scalar(select(Plan).where(Plan.code=="pro"))
    if not plan:
        plan=Plan(code="pro",name="Impacto Care",monthly_price=Decimal("59.90"),annual_monthly_price=Decimal("39.90")); db.add(plan); db.flush()
    db.add(Subscription(organization_id=org.id,plan_id=plan.id,status=SubscriptionStatus.TRIAL,billing_cycle=BillingCycle.MONTHLY,current_period_end=(datetime.now(timezone.utc)+timedelta(days=operational.trial_days)).date())); db.commit()
    send_verification_email(user.id,user.email)
    return Message(message="Cadastro realizado. Verifique seu e-mail para ativar a conta.")
@router.get("/auth/verify-email",response_model=Message)
def verify_email(token:str,db:Session=Depends(get_db)):
    user_id=decode_email_token(token); user=db.get(User,user_id) if user_id else None
    if not user: raise HTTPException(400,"Link de confirmação inválido ou expirado")
    if user.email_verified_at is None: user.email_verified_at=datetime.now(timezone.utc); product_event(db,user,"email_confirmed","email"); db.commit()
    return Message(message="E-mail confirmado com sucesso. Você já pode entrar.")
@router.post("/auth/resend-verification",response_model=Message)
def resend_verification(data:EmailAction,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if user and user.email_verified_at is None: send_verification_email(user.id,user.email)
    return Message(message="Se houver uma conta pendente, enviaremos um novo link de confirmação.")
@router.post("/auth/login",response_model=Token)
def login(data:Login,request:Request,db:Session=Depends(get_db)):
    remote_ip=request.client.host if request.client else None
    if not verify_turnstile(data.captcha_token,remote_ip):
        raise HTTPException(400,"Não foi possível validar a verificação de segurança. Tente novamente.")
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"E-mail ou senha inválidos")
    if user.email_verified_at is None: raise HTTPException(403,"Confirme seu e-mail antes de entrar")
    user.last_login_at=datetime.now(timezone.utc)
    if not user.first_access_at: user.first_access_at=user.last_login_at; product_event(db,user,"first_login","password")
    db.commit()
    return Token(access_token=create_token(user.id))
@router.post("/auth/google",response_model=Token)
def google_auth(data:GoogleAuth,db:Session=Depends(get_db)):
    operational=platform_settings(db)
    if not operational.google_login_enabled: raise HTTPException(503,"Login com Google temporariamente desativado")
    if not settings.google_oauth_client_id:
        raise HTTPException(503,"Login com Google ainda não está configurado")
    try:
        identity=google_id_token.verify_oauth2_token(data.credential,google_requests.Request(),settings.google_oauth_client_id)
    except Exception:
        raise HTTPException(401,"Credencial do Google inválida")
    if not identity.get("email_verified"):
        raise HTTPException(401,"O Google não confirmou este e-mail")
    subject=str(identity["sub"]); email=str(identity["email"]).lower()
    google_identity=db.scalar(select(GoogleIdentity).where(GoogleIdentity.subject==subject))
    user=db.get(User,google_identity.user_id) if google_identity else None
    if not user:
        user=db.scalar(select(User).where(User.email==email))
        if user:
            linked=db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id==user.id))
            if linked and linked.subject!=subject: raise HTTPException(409,"Esta conta já está vinculada a outro acesso Google")
            if not linked: db.add(GoogleIdentity(user_id=user.id,subject=subject))
            if user.email_verified_at is None: user.email_verified_at=datetime.now(timezone.utc)
        else:
            required=(data.organization_name,data.phone,data.cpf,data.profession,data.city,data.state)
            if not data.accept_lgpd or any(not value for value in required):
                raise HTTPException(422,"Preencha os dados profissionais e aceite o aviso de privacidade para criar a conta")
            if data.profession not in PROFESSIONS:
                raise HTTPException(422,"Profissão inválida")
            org=Organization(name=data.organization_name); db.add(org); db.flush()
            profile=data.model_dump(exclude={"credential","organization_name","accept_lgpd"})
            profile["state"]=str(data.state).upper()
            if profile.get("council_state"): profile["council_state"]=str(profile["council_state"]).upper()
            user=User(**profile,name=str(identity.get("name") or email.split("@")[0]),email=email,password_hash=hash_password(secrets.token_urlsafe(48)),email_verified_at=datetime.now(timezone.utc),role=Role.PROFESSIONAL,organization_id=org.id,registration_source="google")
            db.add(user); db.flush(); db.add(GoogleIdentity(user_id=user.id,subject=subject))
            plan=db.scalar(select(Plan).where(Plan.code=="pro"))
            if not plan:
                plan=Plan(code="pro",name="Impacto Care",monthly_price=Decimal("59.90"),annual_monthly_price=Decimal("39.90")); db.add(plan); db.flush()
            db.add(Subscription(organization_id=org.id,plan_id=plan.id,status=SubscriptionStatus.TRIAL,billing_cycle=BillingCycle.MONTHLY,current_period_end=(datetime.now(timezone.utc)+timedelta(days=operational.trial_days)).date()))
    if not user.is_active: raise HTTPException(403,"Conta desativada")
    user.last_login_at=datetime.now(timezone.utc)
    if not user.first_access_at: user.first_access_at=user.last_login_at; product_event(db,user,"first_login","google")
    db.commit()
    return Token(access_token=create_token(user.id))

@router.post("/auth/forgot-password",response_model=Message)
def forgot_password(data:EmailAction,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if user: send_password_reset_email(user.id,user.email)
    return Message(message="Se o e-mail estiver cadastrado, enviaremos as instruções.")
@router.post("/auth/reset-password",response_model=Message)
def reset_password(data:PasswordReset,db:Session=Depends(get_db)):
    user_id=decode_password_reset_token(data.token); user=db.get(User,user_id) if user_id else None
    if not user: raise HTTPException(400,"Link inválido ou expirado")
    user.password_hash=hash_password(data.password)
    if user.email_verified_at is None: user.email_verified_at=datetime.now(timezone.utc)
    db.commit()
    return Message(message="Senha redefinida com sucesso.")
@router.get("/me",response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@router.get("/onboarding",response_model=OnboardingStatus)
def onboarding(user:User=Depends(professional),db:Session=Depends(get_db)):
    result=onboarding_status(db,user);db.commit();return result
@router.get("/context-messages")
def context_messages(user:User=Depends(professional),db:Session=Depends(get_db)):
    progress=onboarding_status(db,user);next_action=progress.get("next_action")
    if not next_action:return []
    code=f"next_{next_action['code']}";interaction=db.scalar(select(ContextMessageInteraction).where(ContextMessageInteraction.user_id==user.id,ContextMessageInteraction.message_code==code))
    if interaction and (interaction.dismissed_at or interaction.views>=3):return []
    return [{"code":code,"title":"Próximo passo recomendado","message":next_action["benefit"],"action_label":next_action["title"],"action_path":next_action["action_path"]}]
@router.post("/context-messages/{message_code}")
def context_message_interaction(message_code:str,data:ContextInteractionIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    item=db.scalar(select(ContextMessageInteraction).where(ContextMessageInteraction.user_id==user.id,ContextMessageInteraction.message_code==message_code))
    if not item:item=ContextMessageInteraction(organization_id=user.organization_id,user_id=user.id,message_code=message_code);db.add(item)
    moment=datetime.now(timezone.utc)
    if data.action=="view":item.views+=1;item.last_viewed_at=moment
    elif data.action=="click":item.clicked_at=moment
    else:item.dismissed_at=moment
    db.commit();return {"updated":True}
@router.get("/me/communications",response_model=CommunicationPreferences)
def communication_preferences(user:User=Depends(current_user)):
    return CommunicationPreferences(email_operational=user.email_operational,email_guidance=user.email_guidance,email_billing=user.email_billing,email_marketing=user.email_marketing,whatsapp_allowed=user.whatsapp_allowed)
@router.put("/me/communications",response_model=CommunicationPreferences)
def update_communication_preferences(data:CommunicationPreferences,user:User=Depends(current_user),db:Session=Depends(get_db)):
    for key,value in data.model_dump().items(): setattr(user,key,value)
    user.communication_consent_at=datetime.now(timezone.utc);user.communication_consent_source="settings";user.communication_consent_version="1.0";db.commit();return data
@router.post("/exit-survey",status_code=201)
def exit_survey(data:ExitSurveyIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    subscription=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id))
    if not subscription:raise HTTPException(404,"Assinatura não encontrada")
    existing=db.scalar(select(ExitSurveyResponse).where(ExitSurveyResponse.user_id==user.id,ExitSurveyResponse.subscription_id==subscription.id))
    if existing:raise HTTPException(409,"Pesquisa já respondida")
    db.add(ExitSurveyResponse(organization_id=user.organization_id,user_id=user.id,subscription_id=subscription.id,reason=data.reason,details=data.details));product_event(db,user,"exit_survey_answered");db.commit();return {"message":"Obrigado. Sua resposta ajudará a melhorar a Impacto Care."}
@router.put("/me/professional-profile",response_model=UserOut)
def update_professional_profile(data:ProfessionalProfileUpdate,user:User=Depends(professional),db:Session=Depends(get_db)):
    for key,value in data.model_dump().items(): setattr(user,key,value)
    if user.professional_summary and user.profession and user.phone: product_event(db,user,"profile_completed")
    audit(db,user,"update","professional_profile");db.commit();db.refresh(user);return user
@router.put("/me/profile-photo",response_model=Message)
def profile_photo(data:ProfilePhotoIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    try: content=base64.b64decode(data.content_base64,validate=True)
    except (binascii.Error,ValueError): raise HTTPException(422,"Imagem inválida")
    if not content or len(content)>1024*1024: raise HTTPException(422,"A foto deve ter no máximo 1 MB")
    user.profile_photo=content;user.profile_photo_content_type=data.content_type;user.profile_photo_updated_at=datetime.now(timezone.utc);db.commit()
    return Message(message="Foto do perfil atualizada")
@router.get("/public/professionals/{professional_id}/photo")
def public_profile_photo(professional_id:str,db:Session=Depends(get_db)):
    user=db.get(User,professional_id)
    if not user or user.role!=Role.PROFESSIONAL or not user.profile_photo: raise HTTPException(404,"Foto não encontrada")
    return Response(content=user.profile_photo,media_type=user.profile_photo_content_type or "image/jpeg",headers={"Cache-Control":"public, max-age=3600"})
@router.get("/dashboard",response_model=Dashboard)
def dashboard(user:User=Depends(professional),db:Session=Depends(get_db)):
    org=user.organization_id; start=datetime.now(timezone.utc); today=start.date(); past=today-timedelta(days=30); future=today+timedelta(days=30)
    patients=db.scalar(select(func.count()).select_from(Patient).where(Patient.organization_id==org,Patient.status=="active")) or 0
    upcoming=db.scalar(select(func.count()).select_from(Visit).where(Visit.organization_id==org,Visit.starts_at>=start,Visit.status==VisitStatus.SCHEDULED)) or 0
    revenue=db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==org,FinanceEntry.entry_type=="income",FinanceEntry.paid.is_(True),FinanceEntry.due_date>=past,FinanceEntry.due_date<=today)) or Decimal(0)
    pending=db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==org,FinanceEntry.entry_type=="income",FinanceEntry.paid.is_(False),FinanceEntry.due_date>=today,FinanceEntry.due_date<=future)) or Decimal(0)
    return Dashboard(patients=patients,upcoming_visits=upcoming,revenue_last_30_days=revenue,receivable_next_30_days=pending)
@router.get("/dashboard/chart",response_model=list[DashboardChartItem])
def dashboard_chart(user:User=Depends(professional),db:Session=Depends(get_db)):
    now_local=datetime.now(LOCAL_TZ); months=[]
    for offset in range(5,-1,-1):
        month_index=now_local.year*12+now_local.month-1-offset;year=month_index//12;month=month_index%12+1
        start=datetime(year,month,1,tzinfo=LOCAL_TZ);next_month=datetime(year+1,1,1,tzinfo=LOCAL_TZ) if month==12 else datetime(year,month+1,1,tzinfo=LOCAL_TZ)
        start_utc=start.astimezone(timezone.utc);end_utc=next_month.astimezone(timezone.utc)
        revenue=db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==user.organization_id,FinanceEntry.entry_type=="income",FinanceEntry.paid.is_(True),FinanceEntry.due_date>=start.date(),FinanceEntry.due_date<next_month.date())) or Decimal(0)
        visits_count=db.scalar(select(func.count()).select_from(Visit).where(Visit.organization_id==user.organization_id,Visit.starts_at>=start_utc,Visit.starts_at<end_utc,Visit.status!=VisitStatus.CANCELED)) or 0
        records_count=db.scalar(select(func.count()).select_from(ServiceRecord).where(ServiceRecord.organization_id==user.organization_id,ServiceRecord.occurred_at>=start_utc,ServiceRecord.occurred_at<end_utc)) or 0
        months.append(DashboardChartItem(label=start.strftime("%b/%y"),revenue=revenue,visits=visits_count,records=records_count))
    return months
@router.get("/dashboard/finance-chart",response_model=list[FinanceChartItem])
def dashboard_finance_chart(days:int=30,user:User=Depends(professional),db:Session=Depends(get_db)):
    days=max(1,min(days,120));today=datetime.now(LOCAL_TZ).date();start=today-timedelta(days=days-1);end=today+timedelta(days=30);rows=[]
    entries=db.scalars(select(FinanceEntry).where(FinanceEntry.organization_id==user.organization_id,FinanceEntry.due_date>=start,FinanceEntry.due_date<=end)).all();by_day={}
    for entry in entries: by_day.setdefault(entry.due_date,[]).append(entry)
    cursor=start
    while cursor<=end:
        daily=by_day.get(cursor,[]);past_or_today=cursor<=today
        rows.append(FinanceChartItem(label=cursor.strftime("%d/%m"),revenue=sum((x.amount for x in daily if x.entry_type=="income" and x.paid and past_or_today),Decimal(0)),expenses=sum((x.amount for x in daily if x.entry_type=="expense" and x.paid and past_or_today),Decimal(0)),projected_revenue=sum((x.amount for x in daily if x.entry_type=="income" and not x.paid and cursor>=today),Decimal(0))))
        cursor+=timedelta(days=1)
    return rows
@router.get("/patients",response_model=list[PatientOut])
def patients(user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(Patient).where(Patient.organization_id==user.organization_id)
    if user.role==Role.FAMILY: q=q.where(Patient.family_user_id==user.id)
    return db.scalars(q.order_by(Patient.name)).all()
@router.post("/patients",response_model=PatientOut,status_code=201)
def create_patient(data:PatientIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    values=data.model_dump(exclude={"responsible"}); item=Patient(**values,organization_id=user.organization_id); db.add(item); db.flush()
    if data.responsible:
        db.add(Responsible(**data.responsible.model_dump(),patient_id=item.id,organization_id=user.organization_id))
    sync_patient_finance(db,item)
    audit(db,user,"create","patient"); db.commit(); db.refresh(item); return item
@router.get("/patients/{patient_id}",response_model=PatientOut)
def get_patient(patient_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=owned(db,Patient,patient_id,user)
    if user.role==Role.FAMILY and item.family_user_id!=user.id: raise HTTPException(403,"Acesso não autorizado")
    return item
@router.patch("/patients/{patient_id}",response_model=PatientOut)
def update_patient(patient_id:str,data:PatientIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    item=owned(db,Patient,patient_id,user)
    for key,value in data.model_dump(exclude={"responsible"}).items(): setattr(item,key,value)
    if data.responsible:
        responsible=db.scalar(select(Responsible).where(Responsible.patient_id==item.id,Responsible.organization_id==user.organization_id))
        if responsible:
            for key,value in data.responsible.model_dump().items(): setattr(responsible,key,value)
        else: db.add(Responsible(**data.responsible.model_dump(),patient_id=item.id,organization_id=user.organization_id))
    sync_patient_finance(db,item); audit(db,user,"update","patient"); db.commit(); db.refresh(item); return item
@router.post("/patients/{patient_id}/portal-invite",response_model=Message)
def invite_patient_portal(patient_id:str,data:PatientPortalInvite,user:User=Depends(professional),db:Session=Depends(get_db)):
    patient=owned(db,Patient,patient_id,user); email=str(data.email).lower()
    family=db.scalar(select(User).where(User.email==email))
    if family and (family.organization_id!=user.organization_id or family.role!=Role.FAMILY): raise HTTPException(409,"Este e-mail já está vinculado a outra conta")
    if not family:
        family=User(organization_id=user.organization_id,name=data.name,email=email,password_hash=hash_password(secrets.token_urlsafe(48)),role=Role.FAMILY)
        db.add(family); db.flush()
    patient.family_user_id=family.id
    responsible=db.scalar(select(Responsible).where(Responsible.patient_id==patient.id,Responsible.organization_id==user.organization_id,Responsible.email==email))
    if responsible: responsible.portal_user_id=family.id
    audit(db,user,"grant_portal_access","patient"); db.commit(); send_password_reset_email(family.id,family.email)
    return Message(message="Convite enviado. O familiar definirá a senha pelo link recebido.")
@router.get("/responsibles",response_model=list[ResponsibleOut])
def responsibles(user:User=Depends(professional),db:Session=Depends(get_db)): return db.scalars(select(Responsible).where(Responsible.organization_id==user.organization_id).order_by(Responsible.name)).all()
@router.post("/responsibles",response_model=ResponsibleOut,status_code=201)
def create_responsible(data:ResponsibleIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    owned(db,Patient,data.patient_id,user); item=Responsible(**data.model_dump(),organization_id=user.organization_id); db.add(item); audit(db,user,"create","responsible"); db.commit(); db.refresh(item); return item
@router.get("/visits",response_model=list[VisitOut])
def visits(user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(Visit).join(Patient).where(Visit.organization_id==user.organization_id)
    if user.role==Role.FAMILY: q=q.where(Patient.family_user_id==user.id)
    return db.scalars(q.order_by(Visit.starts_at)).all()
@router.post("/visits",response_model=VisitOut,status_code=201)
def create_visit(data:VisitIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    owned(db,Patient,data.patient_id,user); item=Visit(**data.model_dump(),professional_id=user.id,organization_id=user.organization_id); db.add(item); audit(db,user,"create","visit"); db.commit(); db.refresh(item); return item
@router.get("/availability",response_model=AvailabilityOut)
def get_availability(user:User=Depends(professional),db:Session=Depends(get_db)):
    windows=db.scalars(select(ProfessionalAvailability).where(ProfessionalAvailability.professional_id==user.id).order_by(ProfessionalAvailability.weekday,ProfessionalAvailability.start_time)).all()
    return AvailabilityOut(default_session_duration_minutes=user.default_session_duration_minutes,windows=windows,signature_name=user.signature_name or user.name,signature_council=user.signature_council or " ".join(filter(None,[user.council_name,user.council_code,user.council_state])),signature_profession=user.signature_profession or user.profession_other or user.profession)
@router.put("/availability",response_model=AvailabilityOut)
def save_availability(data:AvailabilitySettings,user:User=Depends(professional),db:Session=Depends(get_db)):
    grouped={}
    for window in data.windows:
        if window.start_time>=window.end_time: raise HTTPException(422,"O horário inicial deve ser anterior ao final")
        grouped.setdefault(window.weekday,[]).append(window)
    for windows in grouped.values():
        ordered=sorted(windows,key=lambda x:x.start_time)
        if any(a.end_time>b.start_time for a,b in zip(ordered,ordered[1:])): raise HTTPException(422,"Existem horários de trabalho sobrepostos")
    db.query(ProfessionalAvailability).filter(ProfessionalAvailability.professional_id==user.id).delete();user.default_session_duration_minutes=data.default_session_duration_minutes;user.signature_name=data.signature_name;user.signature_council=data.signature_council;user.signature_profession=data.signature_profession
    for window in data.windows: db.add(ProfessionalAvailability(**window.model_dump(),professional_id=user.id,organization_id=user.organization_id))
    audit(db,user,"update","availability");db.commit();return get_availability(user,db)
@router.get("/availability/free-slots",response_model=list[AvailableSlot])
def professional_free_slots(date_from:date|None=None,date_to:date|None=None,user:User=Depends(professional),db:Session=Depends(get_db)):
    start=date_from or datetime.now(LOCAL_TZ).date();end=min(date_to or start+timedelta(days=6),start+timedelta(days=30));duration=user.default_session_duration_minutes;result=[];day=start
    range_start=datetime.combine(start,time.min,tzinfo=LOCAL_TZ).astimezone(timezone.utc);range_end=datetime.combine(end,time.max,tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    visits=db.scalars(select(Visit).where(Visit.professional_id==user.id,Visit.status!=VisitStatus.CANCELED,Visit.starts_at>=range_start-timedelta(hours=8),Visit.starts_at<=range_end)).all()
    while day<=end:
        windows=db.scalars(select(ProfessionalAvailability).where(ProfessionalAvailability.professional_id==user.id,ProfessionalAvailability.weekday==day.weekday(),ProfessionalAvailability.is_active.is_(True))).all()
        for window in windows:
            candidate=datetime.combine(day,window.start_time,tzinfo=LOCAL_TZ);window_end=datetime.combine(day,window.end_time,tzinfo=LOCAL_TZ)
            while candidate+timedelta(minutes=duration)<=window_end:
                candidate_utc=candidate.astimezone(timezone.utc);candidate_end=candidate_utc+timedelta(minutes=duration);busy=False
                for visit in visits:
                    visit_start=visit.starts_at.replace(tzinfo=timezone.utc) if visit.starts_at.tzinfo is None else visit.starts_at
                    if visit_start<candidate_end and visit_start+timedelta(minutes=visit.duration_minutes)>candidate_utc: busy=True;break
                if candidate>datetime.now(LOCAL_TZ) and not busy: result.append(AvailableSlot(starts_at=candidate,ends_at=candidate+timedelta(minutes=duration)))
                candidate+=timedelta(minutes=duration)
        day+=timedelta(days=1)
    return result
@router.post("/visits/{visit_id}/confirmation-link",response_model=VisitConfirmationLink)
def confirmation_link(visit_id:str,user:User=Depends(professional),db:Session=Depends(get_db)):
    item=owned(db,Visit,visit_id,user);url=ensure_confirmation_url(db,item);item.confirmation_manual_sent_at=datetime.now(timezone.utc);audit(db,user,"send_manual_confirmation","visit");db.commit();return VisitConfirmationLink(url=url)
@router.get("/visits/{visit_id}/ai-analyses",response_model=list[AIAnalysisOut])
def visit_ai_analyses(visit_id:str,user:User=Depends(professional),db:Session=Depends(get_db)):
    owned(db,Visit,visit_id,user);return db.scalars(select(AIAnalysis).where(AIAnalysis.visit_id==visit_id).order_by(AIAnalysis.created_at)).all()
@router.post("/visits/{visit_id}/ai-analysis",response_model=AIAnalysisOut)
def create_visit_ai_analysis(visit_id:str,data:AIAnalysisCreate,user:User=Depends(professional),db:Session=Depends(get_db)):
    visit=owned(db,Visit,visit_id,user);existing=db.scalar(select(AIAnalysis).where(AIAnalysis.visit_id==visit.id,AIAnalysis.analysis_type==data.analysis_type))
    if existing: return existing
    limit,used=ai_limit(db,user)
    if limit<=0 or used>=limit: raise HTTPException(429,f"Limite diário de IA atingido ({used}/{limit}).")
    records=db.scalars(select(ServiceRecord).where(ServiceRecord.patient_id==visit.patient_id,ServiceRecord.organization_id==user.organization_id).order_by(ServiceRecord.occurred_at.desc()).limit(6)).all()
    if data.analysis_type=="evolution" and not any(record.visit_id==visit.id for record in records): raise HTTPException(409,"Salve o registro deste atendimento antes de gerar a evolução.")
    patient=visit.patient
    context={"conditions":patient.conditions,"medications":patient.medications,"allergies":patient.allergies,"care_needs":patient.care_needs,"mobility":patient.mobility,"scheduled_at":visit.starts_at.isoformat(),"recent_records":[{"occurred_at":record.occurred_at.isoformat(),"summary":record.summary,"guidance":record.guidance,"weight_kg":str(record.weight_kg) if record.weight_kg else None,"blood_pressure":f"{record.blood_pressure_systolic}/{record.blood_pressure_diastolic}" if record.blood_pressure_systolic and record.blood_pressure_diastolic else None,"heart_rate":record.heart_rate_bpm,"temperature":str(record.temperature_c) if record.temperature_c else None,"oxygen_saturation":record.oxygen_saturation_percent} for record in records]}
    content,usage=generate_analysis(data.analysis_type,context)
    item=AIAnalysis(organization_id=user.organization_id,visit_id=visit.id,patient_id=visit.patient_id,professional_id=user.id,analysis_type=data.analysis_type,content=content,model=settings.openai_model,input_tokens=usage.get("input_tokens"),output_tokens=usage.get("output_tokens"));db.add(item);audit(db,user,"generate",f"ai_{data.analysis_type}");db.commit();db.refresh(item);return item
@router.get("/public/visits/{token}",response_model=PublicVisitOut)
def public_visit(token:str,db:Session=Depends(get_db)):
    item=visit_by_token(db,token);professional_user=db.get(User,item.professional_id)
    return PublicVisitOut(patient_name=item.patient.name,professional_name=professional_user.name,starts_at=item.starts_at,duration_minutes=item.duration_minutes,status=item.status,patient_response=item.patient_response)
@router.get("/public/visits/{token}/available-slots",response_model=list[AvailableSlot])
def public_slots(token:str,date_from:date|None=None,date_to:date|None=None,db:Session=Depends(get_db)):
    item=visit_by_token(db,token);start=date_from or datetime.now(LOCAL_TZ).date();end=min(date_to or start+timedelta(days=14),start+timedelta(days=30));duration=db.get(User,item.professional_id).default_session_duration_minutes;result=[]
    day=start
    while day<=end:
        for window in db.scalars(select(ProfessionalAvailability).where(ProfessionalAvailability.professional_id==item.professional_id,ProfessionalAvailability.weekday==day.weekday(),ProfessionalAvailability.is_active.is_(True))).all():
            candidate=datetime.combine(day,window.start_time,tzinfo=LOCAL_TZ)
            while candidate+timedelta(minutes=duration)<=datetime.combine(day,window.end_time,tzinfo=LOCAL_TZ):
                if candidate>datetime.now(LOCAL_TZ) and slot_is_available(db,item,candidate,duration): result.append(AvailableSlot(starts_at=candidate,ends_at=candidate+timedelta(minutes=duration)))
                candidate+=timedelta(minutes=duration)
        day+=timedelta(days=1)
    return result
@router.post("/public/visits/{token}/response",response_model=PublicVisitOut)
def public_visit_response(token:str,data:VisitResponseIn,db:Session=Depends(get_db)):
    item=visit_by_token(db,token)
    if item.status==VisitStatus.COMPLETED: raise HTTPException(409,"Este atendimento já foi concluído")
    professional_user=db.get(User,item.professional_id);old=item.starts_at
    if data.action=="confirm": item.patient_response="confirmed"
    elif data.action=="cancel": item.status=VisitStatus.CANCELED;item.patient_response="canceled"
    else:
        if not data.new_starts_at: raise HTTPException(422,"Selecione um novo horário")
        duration=professional_user.default_session_duration_minutes
        if not slot_is_available(db,item,data.new_starts_at,duration): raise HTTPException(409,"Este horário não está mais disponível")
        item.starts_at=data.new_starts_at;item.duration_minutes=duration;item.status=VisitStatus.SCHEDULED;item.patient_response="rescheduled"
    item.patient_responded_at=datetime.now(timezone.utc);db.commit();db.refresh(item)
    if data.action in {"cancel","reschedule"}:
        fmt=lambda value:value.astimezone(LOCAL_TZ).strftime("%d/%m/%Y às %H:%M")
        send_visit_change_email(professional_user.email,professional_user.name,item.patient.name,data.action,fmt(old),fmt(item.starts_at) if data.action=="reschedule" else None)
    return PublicVisitOut(patient_name=item.patient.name,professional_name=professional_user.name,starts_at=item.starts_at,duration_minutes=item.duration_minutes,status=item.status,patient_response=item.patient_response)
@router.post("/visits/{visit_id}/cancel",response_model=VisitOut)
def cancel_visit(visit_id:str,user:User=Depends(professional),db:Session=Depends(get_db)):
    item=owned(db,Visit,visit_id,user)
    if item.status==VisitStatus.COMPLETED: raise HTTPException(409,"Atendimento concluído não pode ser cancelado")
    item.status=VisitStatus.CANCELED; audit(db,user,"cancel","visit"); db.commit(); db.refresh(item); return item
@router.get("/records",response_model=list[RecordOut])
def records(user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(ServiceRecord).join(Patient).where(ServiceRecord.organization_id==user.organization_id)
    if user.role==Role.FAMILY: q=q.where(Patient.family_user_id==user.id)
    return db.scalars(q.order_by(ServiceRecord.occurred_at.desc())).all()
@router.get("/records/{record_id}",response_model=RecordOut)
def record_detail(record_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=owned(db,ServiceRecord,record_id,user)
    if user.role==Role.FAMILY and item.patient.family_user_id!=user.id: raise HTTPException(403,"Acesso não autorizado")
    return item
@router.get("/records/{record_id}/pdf")
def record_pdf(record_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=owned(db,ServiceRecord,record_id,user)
    if user.role==Role.FAMILY and item.patient.family_user_id!=user.id: raise HTTPException(403,"Acesso não autorizado")
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name="Notice",parent=styles["BodyText"],fontSize=8,textColor=colors.HexColor("#555555"),borderColor=colors.HexColor("#dddddd"),borderWidth=1,borderPadding=8,spaceBefore=12))
    buffer=io.BytesIO();document=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=2*cm,leftMargin=2*cm,topMargin=2*cm,bottomMargin=2*cm,title="Registro de atendimento")
    safe=lambda value:html.escape(str(value or "—")).replace("\n","<br/>")
    story=[Paragraph("Impacto Care",styles["Title"]),Paragraph("Registro de atendimento",styles["Heading1"]),Spacer(1,10),Table([["Paciente",safe(item.patient.name)],["Data",item.occurred_at.astimezone(LOCAL_TZ).strftime("%d/%m/%Y às %H:%M")]],colWidths=[4*cm,11*cm],style=TableStyle([("GRID",(0,0),(-1,-1),.5,colors.HexColor("#dddddd")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#e8f5f1")),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),7)])),Spacer(1,14)]
    vitals=[]
    for label,value in [("Peso",f"{item.weight_kg} kg" if item.weight_kg else None),("Pressão arterial",f"{item.blood_pressure_systolic}/{item.blood_pressure_diastolic}" if item.blood_pressure_systolic and item.blood_pressure_diastolic else None),("Frequência cardíaca",f"{item.heart_rate_bpm} bpm" if item.heart_rate_bpm else None),("Frequência respiratória",f"{item.respiratory_rate_bpm} irpm" if item.respiratory_rate_bpm else None),("Temperatura",f"{item.temperature_c} °C" if item.temperature_c else None),("Saturação",f"{item.oxygen_saturation_percent}%" if item.oxygen_saturation_percent else None),("Glicemia",f"{item.blood_glucose_mg_dl} mg/dL" if item.blood_glucose_mg_dl else None)]:
        if value: vitals.append([label,value])
    if vitals: story.extend([Paragraph("Peso e sinais vitais informados",styles["Heading2"]),Table(vitals,colWidths=[6*cm,9*cm],style=TableStyle([("GRID",(0,0),(-1,-1),.5,colors.HexColor("#dddddd")),("PADDING",(0,0),(-1,-1),6)])),Spacer(1,12)])
    story.extend([Paragraph("Descrição do atendimento",styles["Heading2"]),Paragraph(safe(item.summary),styles["BodyText"]),Spacer(1,12),Paragraph("Orientações",styles["Heading2"]),Paragraph(safe(item.guidance),styles["BodyText"]),Spacer(1,22),Paragraph(safe(item.professional_signature_name),styles["Heading3"]),Paragraph(safe(" · ".join(filter(None,[item.professional_signature_profession,item.professional_signature_council]))),styles["BodyText"]),Paragraph("Este documento é apenas um registro administrativo do atendimento, não possui valor legal e não substitui documentos clínicos oficiais, avaliações ou orientações emitidas por profissionais habilitados.",styles["Notice"])])
    document.build(story);return Response(content=buffer.getvalue(),media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="atendimento-{item.id}.pdf"'})
@router.post("/records",response_model=RecordOut,status_code=201)
def create_record(data:RecordIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    owned(db,Patient,data.patient_id,user); values=data.model_dump(exclude_none=True); item=ServiceRecord(**values,professional_id=user.id,organization_id=user.organization_id,professional_signature_name=user.signature_name or user.name,professional_signature_council=user.signature_council or " ".join(filter(None,[user.council_name,user.council_code,user.council_state])),professional_signature_profession=user.signature_profession or user.profession_other or user.profession); db.add(item); audit(db,user,"create","service_record"); db.commit(); db.refresh(item); return item
@router.get("/finance",response_model=list[FinanceOut])
def finance(user:User=Depends(professional),db:Session=Depends(get_db)): return db.scalars(select(FinanceEntry).where(FinanceEntry.organization_id==user.organization_id).order_by(FinanceEntry.due_date.desc())).all()
@router.post("/finance",response_model=FinanceOut,status_code=201)
def create_finance(data:FinanceIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    if data.patient_id: owned(db,Patient,data.patient_id,user)
    item=FinanceEntry(**data.model_dump(),organization_id=user.organization_id); db.add(item); audit(db,user,"create","finance"); db.commit(); db.refresh(item); return item
@router.get("/vehicles",response_model=list[VehicleOut])
def vehicles(user:User=Depends(professional),db:Session=Depends(get_db)):
    return db.scalars(select(Vehicle).where(Vehicle.organization_id==user.organization_id).order_by(Vehicle.is_default.desc(),Vehicle.name)).all()
@router.post("/vehicles",response_model=VehicleOut,status_code=201)
def create_vehicle(data:VehicleIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    if data.is_default: db.query(Vehicle).filter(Vehicle.organization_id==user.organization_id).update({Vehicle.is_default:False})
    item=Vehicle(**data.model_dump(),organization_id=user.organization_id); db.add(item); audit(db,user,"create","vehicle"); db.commit(); db.refresh(item); return item
@router.post("/routes/calculate")
def route_calculate(data:RouteCalculate,user:User=Depends(professional),db:Session=Depends(get_db)):
    vehicle=owned(db,Vehicle,data.vehicle_id,user) if data.vehicle_id else None
    average=Decimal(vehicle.average_km_per_liter) if vehicle else Decimal(data.average_km_per_liter)
    fuel_price=Decimal(vehicle.fuel_price) if vehicle else Decimal(data.fuel_price)
    additional=Decimal(vehicle.additional_cost_per_km) if vehicle else Decimal(data.additional_cost_per_km)
    local_tz=ZoneInfo("America/Sao_Paulo"); start=datetime.combine(data.date,time.min,tzinfo=local_tz).astimezone(timezone.utc); end=datetime.combine(data.date,time.max,tzinfo=local_tz).astimezone(timezone.utc)
    visits=db.scalars(select(Visit).join(Patient).where(Visit.organization_id==user.organization_id,Visit.starts_at>=start,Visit.starts_at<=end,Visit.status==VisitStatus.SCHEDULED).order_by(Visit.starts_at)).all()
    if not visits: raise HTTPException(422,"Não há visitas agendadas para esta data")
    start_point=geocode(data.start_address); points=[start_point]; stops=[]
    for visit in visits:
        patient=visit.patient
        if patient.latitude is None or patient.longitude is None:
            address=", ".join(filter(None,[patient.address,patient.address_number,patient.neighborhood,patient.city,patient.state,"Brasil"]))
            if not patient.address or not patient.city: raise HTTPException(422,f"Complete o endereço de {patient.name}")
            patient.latitude,patient.longitude=geocode(address)
        points.append((patient.latitude,patient.longitude)); stops.append({"input_index":len(points)-1,"visit_id":visit.id,"patient_id":patient.id,"patient_name":patient.name,"scheduled_at":visit.starts_at,"duration_minutes":visit.duration_minutes,"address":", ".join(filter(None,[patient.address,patient.address_number,patient.city,patient.state]))})
    route_points=points if data.optimize_order or not data.return_to_start else points+[start_point]
    calculated=calculate_route(route_points,data.return_to_start,data.optimize_order); route=calculated["route"]; order=calculated["order"]
    rate=fuel_price/average+additional; ordered_stops=[]; return_cost=Decimal(0)
    stop_by_index={stop["input_index"]:stop for stop in stops}
    for leg_index,leg in enumerate(route["legs"]):
        destination=order[(leg_index+1)%len(order)] if data.optimize_order else leg_index+1
        cost=money(Decimal(str(leg["distance"]))/Decimal(1000)*rate)
        if destination in stop_by_index: ordered_stops.append({**stop_by_index[destination],"leg_distance_km":round(leg["distance"]/1000,2),"leg_duration_minutes":round(leg["duration"]/60),"leg_cost":cost})
        else: return_cost+=cost
    total_km=Decimal(str(route["distance"]))/Decimal(1000); fuel_liters=total_km/average; db.commit()
    return {"date":data.date,"total_distance_km":round(float(total_km),2),"total_duration_minutes":round(route["duration"]/60),"estimated_fuel_liters":float(fuel_liters.quantize(Decimal("0.01"))),"fuel_cost":money(fuel_liters*fuel_price),"additional_cost":money(total_km*additional),"total_cost":money(total_km*rate),"return_cost":money(return_cost),"stops":ordered_stops,"geometry":route["geometry"]}
def intake_by_token(db:Session,token:str):
    item=db.scalar(select(IntakeRequest).where(IntakeRequest.token_hash==hashlib.sha256(token.encode()).hexdigest()))
    expires=item.expires_at.replace(tzinfo=timezone.utc) if item and item.expires_at.tzinfo is None else item.expires_at if item else None
    if not item or expires<datetime.now(timezone.utc): raise HTTPException(404,"Link inválido ou expirado")
    return item
@router.post("/intakes",status_code=201)
def create_intake_link(data:IntakeLinkCreate,user:User=Depends(professional),db:Session=Depends(get_db)):
    token=secrets.token_urlsafe(32); item=IntakeRequest(organization_id=user.organization_id,created_by_id=user.id,recipient_name=data.recipient_name,recipient_phone=data.recipient_phone,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=datetime.now(timezone.utc)+timedelta(days=data.expires_in_days));db.add(item);audit(db,user,"create","intake_link");db.commit();db.refresh(item)
    return {"id":item.id,"status":item.status,"expires_at":item.expires_at,"url":f"{settings.frontend_url.rstrip('/')}/avaliacao/{token}"}
@router.get("/intakes")
def list_intakes(user:User=Depends(professional),db:Session=Depends(get_db)):
    items=db.scalars(select(IntakeRequest).where(IntakeRequest.organization_id==user.organization_id).order_by(IntakeRequest.created_at.desc())).all()
    return [{"id":x.id,"status":x.status,"expires_at":x.expires_at,"submitted_at":x.submitted_at,"patient_id":x.patient_id,"patient_name":(x.family_data or {}).get("patient_name"),"recipient_name":x.recipient_name,"recipient_phone":x.recipient_phone} for x in items]
@router.get("/public/intakes/{token}")
def public_intake(token:str,db:Session=Depends(get_db)):
    item=intake_by_token(db,token); creator=db.get(User,item.created_by_id)
    return {"professional_name":creator.name,"status":item.status,"expires_at":item.expires_at}
@router.post("/public/intakes/{token}",status_code=201)
def submit_intake(token:str,data:IntakeSubmit,db:Session=Depends(get_db)):
    item=intake_by_token(db,token)
    if item.status!="pending": raise HTTPException(409,"Este formulário já foi enviado")
    if not data.accept_privacy: raise HTTPException(422,"É necessário aceitar o aviso de privacidade")
    values=data.model_dump(mode="json"); notes="\n\n".join(f"{label}: {values.get(field)}" for label,field in [("Condições informadas","conditions"),("Medicamentos","medications"),("Alergias","allergies"),("Necessidades","needs"),("Mobilidade","mobility"),("Informações adicionais","additional_information")] if values.get(field))
    patient=Patient(organization_id=item.organization_id,status="inactive",name=data.patient_name,birth_date=data.birth_date,cpf=data.cpf,gender=data.gender,phone=data.phone,email=str(data.email) if data.email else None,postal_code=data.postal_code,address=data.address,address_number=data.address_number,address_complement=data.address_complement,neighborhood=data.neighborhood,city=data.city,state=data.state,conditions=data.conditions,medications=data.medications,allergies=data.allergies,care_needs=data.needs,mobility=data.mobility,notes=data.additional_information or notes or None);db.add(patient);db.flush()
    db.add(Responsible(organization_id=item.organization_id,patient_id=patient.id,name=data.responsible_name,relationship=data.responsible_relationship,phone=data.responsible_phone,email=str(data.responsible_email) if data.responsible_email else None));item.status="submitted";item.submitted_at=datetime.now(timezone.utc);item.patient_id=patient.id;item.family_data=values;db.commit()
    return {"message":"Informações enviadas ao profissional com sucesso.","patient_id":patient.id}
@router.post("/patients/{patient_id}/activate")
def activate_patient(patient_id:str,user:User=Depends(professional),db:Session=Depends(get_db)):
    patient=owned(db,Patient,patient_id,user);patient.status="active";audit(db,user,"activate","patient");db.commit();return {"message":"Paciente ativado com sucesso"}
@router.get("/reports/summary")
def report_summary(user:User=Depends(professional),db:Session=Depends(get_db)):
    org=user.organization_id
    by_status=db.execute(select(Visit.status,func.count()).where(Visit.organization_id==org).group_by(Visit.status)).all()
    return {"generated_at":datetime.now(timezone.utc),"visits_by_status":{str(k.value):v for k,v in by_status},"service_records":db.scalar(select(func.count()).select_from(ServiceRecord).where(ServiceRecord.organization_id==org)) or 0,"total_received":db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==org,FinanceEntry.paid.is_(True))) or 0}

def ensure_subscription(db:Session,user:User)->Subscription:
    """Backfill the trial subscription for accounts created before billing existed."""
    item=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id))
    if item:
        return item
    plan=db.scalar(select(Plan).where(Plan.code=="pro"))
    if not plan:
        plan=Plan(code="pro",name="Impacto Care",monthly_price=Decimal("59.90"),annual_monthly_price=Decimal("39.90"))
        db.add(plan)
        db.flush()
    item=Subscription(
        organization_id=user.organization_id,
        plan_id=plan.id,
        status=SubscriptionStatus.TRIAL,
        billing_cycle=BillingCycle.MONTHLY,
        current_period_end=(datetime.now(timezone.utc)+timedelta(days=platform_settings(db).trial_days)).date(),
    )
    db.add(item)
    db.flush()
    return item

@router.get("/billing/subscription")
def subscription(user:User=Depends(account_professional),db:Session=Depends(get_db)):
    item=ensure_subscription(db,user)
    db.commit()
    plan=db.get(Plan,item.plan_id)
    limit,used=ai_limit(db,user)
    return {"id":item.id,"status":item.status,"billing_cycle":item.billing_cycle,"current_period_end":item.current_period_end,"plan":{"code":plan.code,"name":plan.name,"monthly_price":plan.monthly_price,"annual_monthly_price":plan.annual_monthly_price,"ai_daily_limit":limit,"whatsapp_monthly_limit":plan.whatsapp_monthly_limit},"ai_used_today":used,"gateway":item.gateway,"cancel_at_period_end":item.cancel_at_period_end,"cancellation_requested_at":item.cancellation_requested_at,**subscription_access(item)}
@router.get("/billing/plans")
def billing_plans(db:Session=Depends(get_db)):
    return [{"code":plan.code,"name":plan.name,"monthly_price":str(plan.monthly_price),"annual_monthly_price":str(plan.annual_monthly_price),"ai_daily_limit":plan.ai_daily_limit,"whatsapp_monthly_limit":plan.whatsapp_monthly_limit} for plan in db.scalars(select(Plan).where(Plan.active.is_(True)).order_by(Plan.monthly_price)).all()]
@router.post("/billing/checkout")
def billing_checkout(data:CheckoutCreate,user:User=Depends(account_professional),db:Session=Depends(get_db)):
    item=ensure_subscription(db,user); plan=db.scalar(select(Plan).where(Plan.code==data.plan_code,Plan.active.is_(True)))
    if not plan: raise HTTPException(404,"Plano não encontrado")
    first_due=item.current_period_end if item.status==SubscriptionStatus.TRIAL and item.current_period_end and item.current_period_end>datetime.now(timezone.utc).date() else datetime.now(timezone.utc).date()
    annual=data.billing_cycle==BillingCycle.ANNUAL; value=Decimal(plan.annual_monthly_price)*12 if annual else Decimal(plan.monthly_price); cycle="YEARLY" if annual else "MONTHLY"
    billing_type="PIX" if data.payment_method=="pix" else "CREDIT_CARD"
    payload={"billingTypes":[billing_type],"chargeTypes":["DETACHED" if data.payment_method=="pix" else "RECURRENT"],"minutesToExpire":60,"externalReference":item.id,"callback":{"successUrl":f"{settings.frontend_url.rstrip('/')}/app/billing?status=success","cancelUrl":f"{settings.frontend_url.rstrip('/')}/app/billing?status=cancel","expiredUrl":f"{settings.frontend_url.rstrip('/')}/app/billing?status=expired"},"items":[{"name":f"Impacto Care - {'Anual' if annual else 'Mensal'}","description":"Plataforma de gestão para profissionais de atendimento domiciliar","quantity":1,"value":float(value)}]}
    if data.payment_method!="pix": payload["subscription"]={"cycle":cycle,"nextDueDate":first_due.isoformat()}
    checkout=create_asaas_checkout(payload); checkout_id=checkout.get("id")
    if not checkout_id: raise HTTPException(502,"Resposta inválida do ASAAS")
    item.gateway="asaas";item.external_id=checkout_id;item.pending_plan_id=plan.id;item.billing_cycle=data.billing_cycle;item.cancel_at_period_end=False;item.cancellation_requested_at=None;db.commit()
    return {"checkout_url":checkout.get("link") or f"{settings.asaas_checkout_url}?id={checkout_id}","expires_in_minutes":60}
@router.post("/billing/cancel")
def cancel_subscription(user:User=Depends(account_professional),db:Session=Depends(get_db)):
    item=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Assinatura não encontrada")
    if item.cancel_at_period_end:
        return {"message":"O cancelamento já está programado.","current_period_end":item.current_period_end,"cancel_at_period_end":True}
    recurring_id=item.external_id if item.external_id and item.external_id.startswith("sub_") else None
    if recurring_id: cancel_asaas_subscription(recurring_id)
    item.cancel_at_period_end=True;item.cancellation_requested_at=datetime.now(timezone.utc)
    audit(db,user,"cancel_at_period_end","subscription");db.commit()
    return {"message":"Cancelamento confirmado. O acesso permanecerá disponível até o fim da vigência já paga.","current_period_end":item.current_period_end,"cancel_at_period_end":True}
@router.post("/webhooks/asaas")
def asaas_webhook(payload:dict,asaas_token:str|None=Header(None,alias="asaas-access-token"),db:Session=Depends(get_db)):
    if not settings.asaas_webhook_token or not asaas_token or not secrets.compare_digest(asaas_token,settings.asaas_webhook_token): raise HTTPException(401,"Webhook não autorizado")
    event_type=str(payload.get("event","")).upper(); payment=payload.get("payment") or {}; event_id=str(payload.get("id") or hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest())
    existing_event=db.scalar(select(BillingWebhookEvent).where(BillingWebhookEvent.event_id==event_id))
    reference=payment.get("externalReference") or payload.get("externalReference")
    item=db.get(Subscription,reference) if reference else None
    # O Checkout ASAAS pode não repetir externalReference no objeto payment. Nesse
    # caso, checkoutSession corresponde ao id devolvido por POST /checkouts e
    # persistido em Subscription.external_id durante a criação do checkout.
    checkout_session=payment.get("checkoutSession") or payload.get("checkoutSession")
    if not item and checkout_session:
        item=db.scalar(select(Subscription).where(Subscription.external_id==str(checkout_session)))
    if existing_event and (not item or item.status==SubscriptionStatus.ACTIVE):
        return {"received":True,"duplicate":True}
    if not existing_event:
        db.add(BillingWebhookEvent(gateway="asaas",event_id=event_id,event_type=event_type,payload=payload))
    if item:
        billing_type=str(payment.get("billingType") or "").upper()
        payment_activates=event_type=="PAYMENT_CONFIRMED" or (event_type=="PAYMENT_RECEIVED" and billing_type!="CREDIT_CARD")
        if payment_activates:
            item.status=SubscriptionStatus.ACTIVE;item.cancel_at_period_end=False;item.cancellation_requested_at=None
            if item.pending_plan_id: item.plan_id=item.pending_plan_id;item.pending_plan_id=None
            days=365 if item.billing_cycle==BillingCycle.ANNUAL else 30;item.current_period_end=(datetime.now(timezone.utc)+timedelta(days=days)).date()
            account_user=db.scalar(select(User).where(User.organization_id==item.organization_id,User.role==Role.PROFESSIONAL).order_by(User.created_at))
            if account_user:
                if not account_user.first_paid_at: account_user.first_paid_at=datetime.now(timezone.utc)
                product_event(db,account_user,"payment_confirmed","asaas",{"cycle":item.billing_cycle.value})
                product_event(db,account_user,"subscription_activated","asaas",{"cycle":item.billing_cycle.value})
            db.query(CommunicationLog).filter(CommunicationLog.organization_id==item.organization_id,CommunicationLog.status.in_(["pending","scheduled"])).update({"status":"canceled","skip_reason":"Pagamento confirmado"},synchronize_session=False)
        elif event_type in {"PAYMENT_OVERDUE","PAYMENT_DUNNING_REQUESTED"}: item.status=SubscriptionStatus.PAST_DUE
        elif event_type in {"PAYMENT_REFUNDED","PAYMENT_DELETED"}: item.status=SubscriptionStatus.CANCELED
        if payment.get("subscription"): item.external_id=payment["subscription"]
    db.commit();return {"received":True}
@router.get("/support/tickets",response_model=list[SupportTicketOut])
def support_tickets(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return db.scalars(select(SupportTicket).where(SupportTicket.organization_id==user.organization_id,SupportTicket.user_id==user.id).order_by(SupportTicket.created_at.desc())).all()

@router.post("/support/tickets",response_model=SupportTicketOut,status_code=201)
def create_support_ticket(data:SupportTicketIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    while True:
        number=f"ICP-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"
        if not db.scalar(select(SupportTicket).where(SupportTicket.ticket_number==number)): break
    item=SupportTicket(ticket_number=number,organization_id=user.organization_id,user_id=user.id,category=data.category,description=data.description.strip())
    db.add(item); audit(db,user,"create","support_ticket"); db.commit(); db.refresh(item)
    organization=db.get(Organization,user.organization_id)
    try:
        if send_support_ticket_email(item.ticket_number,item.category,item.description,user.name,user.email,organization.name if organization else user.organization_id):
            item.email_sent_at=datetime.now(timezone.utc); db.commit(); db.refresh(item)
    except (OSError,TimeoutError) as error:
        logging.getLogger(__name__).exception("Falha ao enviar chamado %s por e-mail",item.ticket_number,exc_info=error)
    return item

@router.get("/admin/overview")
def admin_overview(user:User=Depends(admin),db:Session=Depends(get_db)):
    return {"organizations":db.scalar(select(func.count()).select_from(Organization)),"users":db.scalar(select(func.count()).select_from(User)),"patients":db.scalar(select(func.count()).select_from(Patient))}
@router.get("/admin/relationship/automations")
def admin_automations(user:User=Depends(admin),db:Session=Depends(get_db)):
    rows=ensure_templates(db);db.commit();result=[]
    for item in rows.values():
        sent=db.scalar(select(func.count()).select_from(CommunicationLog).where(CommunicationLog.automation_id==item.id,CommunicationLog.status=="sent")) or 0
        failed=db.scalar(select(func.count()).select_from(CommunicationLog).where(CommunicationLog.automation_id==item.id,CommunicationLog.status=="failed")) or 0
        last=db.scalar(select(func.max(CommunicationLog.attempted_at)).where(CommunicationLog.automation_id==item.id))
        result.append({"id":item.id,"code":item.code,"name":item.name,"channel":item.channel,"trigger_type":item.trigger_type,"offset_days":item.offset_days,"subject":item.subject,"content":item.content,"action_path":item.action_path,"is_active":item.is_active,"promotional":item.promotional,"sent":sent,"failed":failed,"last_run_at":last})
    return result
@router.patch("/admin/relationship/automations/{automation_id}")
def admin_update_automation(automation_id:str,data:AutomationUpdate,user:User=Depends(admin),db:Session=Depends(get_db)):
    item=db.get(CommunicationAutomation,automation_id)
    if not item:raise HTTPException(404,"Automação não encontrada")
    for key,value in data.model_dump(exclude_none=True).items():setattr(item,key,value)
    audit(db,user,"update","relationship_automation");db.commit();return {"updated":True}
@router.get("/admin/relationship/logs")
def admin_communication_logs(status:str|None=None,limit:int=100,user:User=Depends(admin),db:Session=Depends(get_db)):
    q=select(CommunicationLog).order_by(CommunicationLog.created_at.desc()).limit(max(1,min(limit,500)))
    if status:q=q.where(CommunicationLog.status==status)
    return [{"id":x.id,"user_id":x.user_id,"template":x.template_code,"channel":x.channel,"status":x.status,"attempts":x.attempts,"scheduled_at":x.scheduled_at,"sent_at":x.sent_at,"error":x.error_message} for x in db.scalars(q).all()]
@router.get("/admin/relationship/metrics")
def admin_relationship_metrics(user:User=Depends(admin),db:Session=Depends(get_db)):
    total=db.scalar(select(func.count()).select_from(User).where(User.role==Role.PROFESSIONAL)) or 0;confirmed=db.scalar(select(func.count()).select_from(User).where(User.role==Role.PROFESSIONAL,User.email_verified_at.is_not(None))) or 0;activated=db.scalar(select(func.count()).select_from(User).where(User.role==Role.PROFESSIONAL,User.activated_at.is_not(None))) or 0;paid=db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status==SubscriptionStatus.ACTIVE)) or 0
    avg_days=db.scalar(select(func.avg(func.extract("epoch",User.activated_at-User.created_at)/86400)).where(User.activated_at.is_not(None))) if db.bind.dialect.name!="sqlite" else None
    by_profession=[{"label":label or "Não informado","registered":count} for label,count in db.execute(select(User.profession,func.count()).where(User.role==Role.PROFESSIONAL).group_by(User.profession)).all()]
    by_source=[{"label":label or "Não informado","registered":count} for label,count in db.execute(select(User.registration_source,func.count()).where(User.role==Role.PROFESSIONAL).group_by(User.registration_source)).all()]
    return {"registered":total,"email_confirmed":confirmed,"activated":activated,"paid":paid,"activation_rate":round(activated/total*100,1) if total else 0,"conversion_rate":round(paid/total*100,1) if total else 0,"average_activation_days":round(float(avg_days),1) if avg_days is not None else None,"messages_sent":db.scalar(select(func.count()).select_from(CommunicationLog).where(CommunicationLog.status=="sent")) or 0,"message_failures":db.scalar(select(func.count()).select_from(CommunicationLog).where(CommunicationLog.status=="failed")) or 0,"by_profession":by_profession,"by_source":by_source}
@router.get("/admin/relationship/exit-surveys")
def admin_exit_surveys(user:User=Depends(admin),db:Session=Depends(get_db)):
    rows=db.execute(select(ExitSurveyResponse.reason,func.count()).group_by(ExitSurveyResponse.reason)).all();return [{"reason":reason,"count":count} for reason,count in rows]
@router.get("/admin/settings")
def admin_get_settings(user:User=Depends(admin),db:Session=Depends(get_db)):
    plan=db.scalar(select(Plan).where(Plan.code=="pro"))
    return {"settings":platform_settings(db).model_dump(mode="json"),"plan":{"name":plan.name,"monthly_price":str(plan.monthly_price),"annual_monthly_price":str(plan.annual_monthly_price),"active":plan.active} if plan else None,"integrations":{"smtp":bool(settings.smtp_host and settings.smtp_username),"google":bool(settings.google_oauth_client_id),"turnstile":bool(settings.turnstile_secret_key),"asaas":bool(settings.asaas_api_key),"asaas_webhook":bool(settings.asaas_webhook_token),"openai":bool(settings.openai_api_key),"whatsapp":bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id),"maps":bool(settings.geocoder_url and settings.routing_url)},"environment":{"frontend_url":settings.frontend_url,"asaas_environment":"produção" if "sandbox" not in settings.asaas_api_url else "homologação"}}
@router.put("/admin/settings",response_model=AdminSettings)
def admin_save_settings(data:AdminSettings,user:User=Depends(admin),db:Session=Depends(get_db)):
    item=db.scalar(select(SystemSetting).where(SystemSetting.key==ADMIN_SETTINGS_KEY))
    if item: item.value=data.model_dump(mode="json");item.updated_by_id=user.id
    else: db.add(SystemSetting(key=ADMIN_SETTINGS_KEY,value=data.model_dump(mode="json"),updated_by_id=user.id))
    audit(db,user,"update","system_settings");db.commit();return data
@router.put("/admin/plan")
def admin_save_plan(data:AdminPlanUpdate,user:User=Depends(admin),db:Session=Depends(get_db)):
    item=db.scalar(select(Plan).where(Plan.code=="pro"))
    if not item: item=Plan(code="pro",**data.model_dump());db.add(item)
    else:
        for key,value in data.model_dump().items(): setattr(item,key,value)
    audit(db,user,"update","plan");db.commit();return {"message":"Plano atualizado"}
@router.patch("/admin/users/{user_id}")
def admin_update_user(user_id:str,data:AdminUserUpdate,user:User=Depends(admin),db:Session=Depends(get_db)):
    account=db.get(User,user_id)
    if not account: raise HTTPException(404,"Usuário não encontrado")
    if account.id==user.id and data.is_active is False: raise HTTPException(409,"O administrador não pode desativar a própria conta")
    if data.is_active is not None: account.is_active=data.is_active
    if data.email_verified is True and account.email_verified_at is None: account.email_verified_at=datetime.now(timezone.utc)
    if data.email_verified is False: account.email_verified_at=None
    subscription=db.scalar(select(Subscription).where(Subscription.organization_id==account.organization_id))
    if data.plan_code or data.billing_cycle or data.complimentary_days is not None:
        if not subscription: raise HTTPException(409,"A conta não possui assinatura para administrar")
        if data.plan_code:
            selected_plan=db.scalar(select(Plan).where(Plan.code==data.plan_code,Plan.active.is_(True)))
            if not selected_plan: raise HTTPException(404,"Plano não encontrado")
            subscription.plan_id=selected_plan.id;subscription.pending_plan_id=None
        if data.billing_cycle: subscription.billing_cycle=data.billing_cycle
        if data.complimentary_days is not None:
            subscription.complimentary_until=datetime.now(LOCAL_TZ).date()+timedelta(days=data.complimentary_days) if data.complimentary_days else None
            subscription.complimentary_note=data.complimentary_note.strip() if data.complimentary_note else None
    audit(db,user,"update","user_access");db.commit();return {"message":"Usuário atualizado"}
@router.get("/admin/support/tickets",response_model=list[SupportTicketOut])
def admin_support_tickets(user:User=Depends(admin),db:Session=Depends(get_db)):
    rows=db.execute(select(SupportTicket,User,Organization).join(User,User.id==SupportTicket.user_id).join(Organization,Organization.id==SupportTicket.organization_id).order_by(SupportTicket.created_at.desc())).all()
    return [{**SupportTicketOut.model_validate(ticket).model_dump(),"requester_name":requester.name,"requester_email":requester.email,"organization_name":organization.name} for ticket,requester,organization in rows]
@router.patch("/admin/support/tickets/{ticket_id}",response_model=SupportTicketOut)
def admin_update_support_ticket(ticket_id:str,data:SupportTicketAdminUpdate,user:User=Depends(admin),db:Session=Depends(get_db)):
    item=db.get(SupportTicket,ticket_id)
    if not item: raise HTTPException(404,"Chamado não encontrado")
    item.admin_response=data.response.strip();item.responded_at=datetime.now(timezone.utc);item.status="closed" if data.close else "answered";item.closed_at=datetime.now(timezone.utc) if data.close else None
    audit(db,user,"respond","support_ticket");db.commit();db.refresh(item);return item

@router.get("/admin/users")
def admin_users(user:User=Depends(admin),db:Session=Depends(get_db)):
    query=(select(User,Organization,Subscription,Plan)
        .join(Organization,Organization.id==User.organization_id)
        .outerjoin(Subscription,Subscription.organization_id==Organization.id)
        .outerjoin(Plan,Plan.id==Subscription.plan_id)
        .order_by(User.created_at.desc()))
    today=datetime.now(timezone.utc).date(); result=[]
    for account,organization,subscription,plan in db.execute(query).all():
        access=subscription_access(subscription,today) if subscription else {"blocked":False,"phase":"no_plan"}
        if not account.is_active: access_status="inactive"
        elif account.email_verified_at is None: access_status="pending_email"
        elif access["blocked"]: access_status="blocked"
        else: access_status=str(access["phase"])
        created_date=subscription.created_at.date() if subscription else None
        result.append({
            "id":account.id,"name":account.name,"email":account.email,"organization":organization.name,
            "role":account.role.value,"profession":account.profession_other or account.profession,
            "is_active":account.is_active,"email_verified":account.email_verified_at is not None,
            "access_status":access_status,"last_login_at":account.last_login_at,"created_at":account.created_at,
            "plan_name":plan.name if plan else None,"plan_status":subscription.status.value if subscription else None,
            "billing_cycle":subscription.billing_cycle.value if subscription else None,
            "plan_started_at":subscription.created_at if subscription else None,
            "plan_ends_at":subscription.current_period_end if subscription else None,
            "plan_days":(today-created_date).days if created_date else None,
            "days_remaining":(subscription.current_period_end-today).days if subscription and subscription.current_period_end else None,
            "complimentary_until":subscription.complimentary_until if subscription else None,
            "complimentary_note":subscription.complimentary_note if subscription else None,
        })
    return result
