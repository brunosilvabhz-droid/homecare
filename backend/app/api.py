from datetime import datetime, timezone, time, timedelta
import hashlib, secrets
import json
from zoneinfo import ZoneInfo
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.deps import current_user, professional, admin
from app.core.security import hash_password, verify_password, create_token, decode_email_token
from app.core.email import send_verification_email
from app.core.routing import geocode, calculate_route, money
from app.core.config import settings
from app.core.billing import create_asaas_checkout
from app.models import Organization, User, Role, Patient, Responsible, Visit, ServiceRecord, FinanceEntry, AuditLog, VisitStatus, Plan, Subscription, SubscriptionStatus, BillingCycle, Vehicle, IntakeRequest, BillingWebhookEvent
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
    db.add(Subscription(organization_id=org.id,plan_id=plan.id,status=SubscriptionStatus.TRIAL,billing_cycle=BillingCycle.MONTHLY,current_period_end=(datetime.now(timezone.utc)+timedelta(days=30)).date())); db.commit()
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
    patients=db.scalar(select(func.count()).select_from(Patient).where(Patient.organization_id==org,Patient.status=="active")) or 0
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
@router.get("/vehicles",response_model=list[VehicleOut])
def vehicles(user:User=Depends(professional),db:Session=Depends(get_db)):
    return db.scalars(select(Vehicle).where(Vehicle.organization_id==user.organization_id).order_by(Vehicle.is_default.desc(),Vehicle.name)).all()
@router.post("/vehicles",response_model=VehicleOut,status_code=201)
def create_vehicle(data:VehicleIn,user:User=Depends(professional),db:Session=Depends(get_db)):
    if data.is_default: db.query(Vehicle).filter(Vehicle.organization_id==user.organization_id).update({Vehicle.is_default:False})
    item=Vehicle(**data.model_dump(),organization_id=user.organization_id); db.add(item); audit(db,user,"create","vehicle"); db.commit(); db.refresh(item); return item
@router.post("/routes/calculate")
def route_calculate(data:RouteCalculate,user:User=Depends(professional),db:Session=Depends(get_db)):
    vehicle=owned(db,Vehicle,data.vehicle_id,user)
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
    rate=Decimal(vehicle.fuel_price)/Decimal(vehicle.average_km_per_liter)+Decimal(vehicle.additional_cost_per_km); ordered_stops=[]; return_cost=Decimal(0)
    stop_by_index={stop["input_index"]:stop for stop in stops}
    for leg_index,leg in enumerate(route["legs"]):
        destination=order[(leg_index+1)%len(order)] if data.optimize_order else leg_index+1
        cost=money(Decimal(str(leg["distance"]))/Decimal(1000)*rate)
        if destination in stop_by_index: ordered_stops.append({**stop_by_index[destination],"leg_distance_km":round(leg["distance"]/1000,2),"leg_duration_minutes":round(leg["duration"]/60),"leg_cost":cost})
        else: return_cost+=cost
    total_km=Decimal(str(route["distance"]))/Decimal(1000); fuel_liters=total_km/Decimal(vehicle.average_km_per_liter); db.commit()
    return {"date":data.date,"vehicle":{"id":vehicle.id,"name":vehicle.name},"total_distance_km":round(float(total_km),2),"total_duration_minutes":round(route["duration"]/60),"estimated_fuel_liters":float(fuel_liters.quantize(Decimal("0.01"))),"fuel_cost":money(fuel_liters*Decimal(vehicle.fuel_price)),"additional_cost":money(total_km*Decimal(vehicle.additional_cost_per_km)),"total_cost":money(total_km*rate),"return_cost":money(return_cost),"stops":ordered_stops,"geometry":route["geometry"]}
def intake_by_token(db:Session,token:str):
    item=db.scalar(select(IntakeRequest).where(IntakeRequest.token_hash==hashlib.sha256(token.encode()).hexdigest()))
    expires=item.expires_at.replace(tzinfo=timezone.utc) if item and item.expires_at.tzinfo is None else item.expires_at if item else None
    if not item or expires<datetime.now(timezone.utc): raise HTTPException(404,"Link inválido ou expirado")
    return item
@router.post("/intakes",status_code=201)
def create_intake_link(data:IntakeLinkCreate,user:User=Depends(professional),db:Session=Depends(get_db)):
    token=secrets.token_urlsafe(32); item=IntakeRequest(organization_id=user.organization_id,created_by_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=datetime.now(timezone.utc)+timedelta(days=data.expires_in_days));db.add(item);audit(db,user,"create","intake_link");db.commit();db.refresh(item)
    return {"id":item.id,"status":item.status,"expires_at":item.expires_at,"url":f"{settings.frontend_url.rstrip('/')}/avaliacao/{token}"}
@router.get("/intakes")
def list_intakes(user:User=Depends(professional),db:Session=Depends(get_db)):
    items=db.scalars(select(IntakeRequest).where(IntakeRequest.organization_id==user.organization_id).order_by(IntakeRequest.created_at.desc())).all()
    return [{"id":x.id,"status":x.status,"expires_at":x.expires_at,"submitted_at":x.submitted_at,"patient_id":x.patient_id,"patient_name":(x.family_data or {}).get("patient_name")} for x in items]
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
    patient=Patient(organization_id=item.organization_id,status="inactive",name=data.patient_name,birth_date=data.birth_date,cpf=data.cpf,gender=data.gender,phone=data.phone,email=str(data.email) if data.email else None,postal_code=data.postal_code,address=data.address,address_number=data.address_number,address_complement=data.address_complement,neighborhood=data.neighborhood,city=data.city,state=data.state,notes=notes or None);db.add(patient);db.flush()
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
@router.get("/billing/subscription")
def subscription(user:User=Depends(professional),db:Session=Depends(get_db)):
    item=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id))
    if not item: raise HTTPException(404,"Assinatura não encontrada")
    plan=db.get(Plan,item.plan_id)
    return {"id":item.id,"status":item.status,"billing_cycle":item.billing_cycle,"current_period_end":item.current_period_end,"plan":{"name":plan.name,"monthly_price":plan.monthly_price,"annual_monthly_price":plan.annual_monthly_price},"gateway":item.gateway}
@router.post("/billing/checkout")
def billing_checkout(data:CheckoutCreate,user:User=Depends(professional),db:Session=Depends(get_db)):
    item=db.scalar(select(Subscription).where(Subscription.organization_id==user.organization_id)); plan=db.get(Plan,item.plan_id) if item else None
    if not item or not plan: raise HTTPException(404,"Assinatura não encontrada")
    first_due=item.current_period_end if item.status==SubscriptionStatus.TRIAL and item.current_period_end and item.current_period_end>datetime.now(timezone.utc).date() else datetime.now(timezone.utc).date()
    annual=data.billing_cycle==BillingCycle.ANNUAL; value=Decimal(plan.annual_monthly_price)*12 if annual else Decimal(plan.monthly_price); cycle="YEARLY" if annual else "MONTHLY"
    payload={"billingTypes":["CREDIT_CARD"],"chargeTypes":["RECURRENT"],"minutesToExpire":60,"externalReference":item.id,"callback":{"successUrl":f"{settings.frontend_url.rstrip('/')}/app/billing?status=success","cancelUrl":f"{settings.frontend_url.rstrip('/')}/app/billing?status=cancel","expiredUrl":f"{settings.frontend_url.rstrip('/')}/app/billing?status=expired"},"items":[{"name":f"Impacto Care - {'Anual' if annual else 'Mensal'}","description":"Plataforma de gestão para profissionais de atendimento domiciliar","quantity":1,"value":float(value)}],"subscription":{"cycle":cycle,"nextDueDate":first_due.isoformat()}}
    checkout=create_asaas_checkout(payload); checkout_id=checkout.get("id")
    if not checkout_id: raise HTTPException(502,"Resposta inválida do ASAAS")
    item.gateway="asaas";item.external_id=checkout_id;item.billing_cycle=data.billing_cycle;db.commit()
    return {"checkout_url":checkout.get("link") or f"{settings.asaas_checkout_url}?id={checkout_id}","expires_in_minutes":60}
@router.post("/webhooks/asaas")
def asaas_webhook(payload:dict,asaas_token:str|None=Header(None,alias="asaas-access-token"),db:Session=Depends(get_db)):
    if not settings.asaas_webhook_token or not asaas_token or not secrets.compare_digest(asaas_token,settings.asaas_webhook_token): raise HTTPException(401,"Webhook não autorizado")
    event_type=str(payload.get("event","")).upper(); payment=payload.get("payment") or {}; event_id=str(payload.get("id") or hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest())
    if db.scalar(select(BillingWebhookEvent).where(BillingWebhookEvent.event_id==event_id)): return {"received":True,"duplicate":True}
    db.add(BillingWebhookEvent(gateway="asaas",event_id=event_id,event_type=event_type,payload=payload))
    reference=payment.get("externalReference") or payload.get("externalReference"); item=db.get(Subscription,reference) if reference else None
    if item:
        if event_type in {"PAYMENT_RECEIVED","PAYMENT_CONFIRMED"}:
            item.status=SubscriptionStatus.ACTIVE;days=365 if item.billing_cycle==BillingCycle.ANNUAL else 30;item.current_period_end=(datetime.now(timezone.utc)+timedelta(days=days)).date()
        elif event_type in {"PAYMENT_OVERDUE","PAYMENT_DUNNING_REQUESTED"}: item.status=SubscriptionStatus.PAST_DUE
        elif event_type in {"PAYMENT_REFUNDED","PAYMENT_DELETED"}: item.status=SubscriptionStatus.CANCELED
        if payment.get("subscription"): item.external_id=payment["subscription"]
    db.commit();return {"received":True}
@router.get("/admin/overview")
def admin_overview(user:User=Depends(admin),db:Session=Depends(get_db)):
    return {"organizations":db.scalar(select(func.count()).select_from(Organization)),"users":db.scalar(select(func.count()).select_from(User)),"patients":db.scalar(select(func.count()).select_from(Patient))}
