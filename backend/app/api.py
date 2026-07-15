from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.deps import current_user, professional, admin
from app.core.security import hash_password, verify_password, create_token, decode_email_token
from app.core.email import send_verification_email
from app.models import Organization, User, Role, Patient, Responsible, Visit, ServiceRecord, FinanceEntry, AuditLog, VisitStatus, Plan, Subscription, SubscriptionStatus, BillingCycle
from app.schemas import *
router=APIRouter()
def audit(db,user,action,resource): db.add(AuditLog(organization_id=user.organization_id,user_id=user.id,action=action,resource=resource))
def owned(db,model,id,user):
    item=db.scalar(select(model).where(model.id==id,model.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Recurso não encontrado")
    return item
@router.post("/auth/register",response_model=Message,status_code=201)
def register(data:Register,db:Session=Depends(get_db)):
    if not data.accept_lgpd: raise HTTPException(422,"É necessário aceitar o consentimento de privacidade")
    if db.scalar(select(User).where(User.email==data.email.lower())): raise HTTPException(409,"E-mail já cadastrado")
    org=Organization(name=data.organization_name); db.add(org); db.flush()
    profile=data.model_dump(exclude={"organization_name","password","accept_lgpd"})
    profile["email"]=str(data.email).lower(); profile["state"]=data.state.upper()
    if profile.get("council_state"): profile["council_state"]=profile["council_state"].upper()
    user=User(**profile,password_hash=hash_password(data.password),role=Role.PROFESSIONAL,organization_id=org.id)
    db.add(user); plan=db.scalar(select(Plan).where(Plan.code=="pro"))
    if not plan:
        plan=Plan(code="pro",name="Impacto Care",monthly_price=Decimal("59.90"),annual_monthly_price=Decimal("39.90")); db.add(plan); db.flush()
    db.add(Subscription(organization_id=org.id,plan_id=plan.id,status=SubscriptionStatus.TRIAL,billing_cycle=BillingCycle.MONTHLY)); db.commit()
    send_verification_email(user.id,user.email)
    return Message(message="Cadastro realizado. Verifique seu e-mail para ativar a conta.")
@router.get("/auth/verify-email",response_model=Message)
def verify_email(token:str,db:Session=Depends(get_db)):
    user_id=decode_email_token(token); user=db.get(User,user_id) if user_id else None
    if not user: raise HTTPException(400,"Link de confirmação inválido ou expirado")
    if user.email_verified_at is None: user.email_verified_at=datetime.now(timezone.utc); db.commit()
    return Message(message="E-mail confirmado com sucesso. Você já pode entrar.")
@router.post("/auth/resend-verification",response_model=Message)
def resend_verification(data:EmailAction,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if user and user.email_verified_at is None: send_verification_email(user.id,user.email)
    return Message(message="Se houver uma conta pendente, enviaremos um novo link de confirmação.")
@router.post("/auth/login",response_model=Token)
def login(data:Login,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email.lower()))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"E-mail ou senha inválidos")
    if user.email_verified_at is None: raise HTTPException(403,"Confirme seu e-mail antes de entrar")
    return Token(access_token=create_token(user.id))
@router.get("/me",response_model=UserOut)
def me(user:User=Depends(current_user)): return user
@router.get("/dashboard",response_model=Dashboard)
def dashboard(user:User=Depends(professional),db:Session=Depends(get_db)):
    org=user.organization_id; start=datetime.now(timezone.utc)
    patients=db.scalar(select(func.count()).select_from(Patient).where(Patient.organization_id==org)) or 0
    upcoming=db.scalar(select(func.count()).select_from(Visit).where(Visit.organization_id==org,Visit.starts_at>=start,Visit.status==VisitStatus.SCHEDULED)) or 0
    revenue=db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==org,FinanceEntry.paid.is_(True))) or Decimal(0)
    pending=db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==org,FinanceEntry.paid.is_(False))) or Decimal(0)
    return Dashboard(patients=patients,upcoming_visits=upcoming,monthly_revenue=revenue,pending_amount=pending)
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
    audit(db,user,"create","patient"); db.commit(); db.refresh(item); return item
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
@router.get("/records",response_model=list[RecordOut])
def records(user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=select(ServiceRecord).join(Patient).where(ServiceRecord.organization_id==user.organization_id)
    if user.role==Role.FAMILY: q=q.where(Patient.family_user_id==user.id)
    return db.scalars(q.order_by(ServiceRecord.occurred_at.desc())).all()
@router.post("/records",response_model=RecordOut,status_code=201)
def create_record(data:RecordIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    owned(db,Patient,data.patient_id,user); values=data.model_dump(exclude_none=True); item=ServiceRecord(**values,professional_id=user.id,organization_id=user.organization_id); db.add(item); audit(db,user,"create","service_record"); db.commit(); db.refresh(item); return item
@router.get("/finance",response_model=list[FinanceOut])
def finance(user:User=Depends(professional),db:Session=Depends(get_db)): return db.scalars(select(FinanceEntry).where(FinanceEntry.organization_id==user.organization_id).order_by(FinanceEntry.due_date.desc())).all()
@router.post("/finance",response_model=FinanceOut,status_code=201)
def create_finance(data:FinanceIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    if data.patient_id: owned(db,Patient,data.patient_id,user)
    item=FinanceEntry(**data.model_dump(),organization_id=user.organization_id); db.add(item); audit(db,user,"create","finance"); db.commit(); db.refresh(item); return item
@router.get("/reports/summary")
def report_summary(user:User=Depends(professional),db:Session=Depends(get_db)):
    org=user.organization_id
    by_status=db.execute(select(Visit.status,func.count()).where(Visit.organization_id==org).group_by(Visit.status)).all()
    return {"generated_at":datetime.now(timezone.utc),"visits_by_status":{str(k.value):v for k,v in by_status},"service_records":db.scalar(select(func.count()).select_from(ServiceRecord).where(ServiceRecord.organization_id==org)) or 0,"total_received":db.scalar(select(func.coalesce(func.sum(FinanceEntry.amount),0)).where(FinanceEntry.organization_id==org,FinanceEntry.paid.is_(True))) or 0}
@router.get("/billing/subscription")
def subscription(user:User=Depends(professional),db:Session=Depends(get_db)):
    item=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Assinatura não encontrada")
    plan=db.get(Plan,item.plan_id)
    return {"id":item.id,"status":item.status,"billing_cycle":item.billing_cycle,"current_period_end":item.current_period_end,"plan":{"name":plan.name,"monthly_price":plan.monthly_price,"annual_monthly_price":plan.annual_monthly_price},"gateway":item.gateway}
@router.get("/admin/overview")
def admin_overview(user:User=Depends(admin),db:Session=Depends(get_db)):
    return {"organizations":db.scalar(select(func.count()).select_from(Organization)),"users":db.scalar(select(func.count()).select_from(User)),"patients":db.scalar(select(func.count()).select_from(Patient))}
