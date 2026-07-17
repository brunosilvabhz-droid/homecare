from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import AIAnalysis, FinanceEntry, Patient, ProductEvent, ProfessionalAvailability, Responsible, ServiceRecord, User, Visit

STEPS=(
    ("email","Confirmar endereço de e-mail","Proteja sua conta e libere todas as comunicações.","/app/profile"),
    ("profile","Completar perfil profissional","Apresente sua experiência e deixe sua página profissional pronta.","/app/profile"),
    ("patient","Cadastrar primeiro paciente","Centralize informações básicas e evite papel, planilhas e mensagens espalhadas.","/app/patients?new=1"),
    ("schedule","Criar primeiro agendamento","Organize seus próximos atendimentos e visualize horários disponíveis.","/app/visits/new"),
    ("record","Criar primeiro registro de atendimento","Organize o histórico administrativo dos atendimentos.","/app/records?new=1"),
    ("pdf","Gerar primeiro PDF","Gere uma versão organizada do registro de atendimento.","/app/records"),
    ("ai","Conhecer o Assistente de IA","Prepare e revise seus atendimentos com apoio da IA.","/app/ai"),
    ("finance","Criar primeiro lançamento financeiro","Acompanhe receitas, despesas e valores pendentes.","/app/finance"),
    ("availability","Configurar disponibilidade","Mostre horários livres e evite conflitos na agenda.","/app/availability"),
    ("family","Conhecer o Portal da Família","Compartilhe somente informações autorizadas com responsáveis.","/app/patients"),
)

def event(db:Session,user:User,name:str,source:str="app",metadata:dict|None=None)->None:
    exists=db.scalar(select(ProductEvent.id).where(ProductEvent.user_id==user.id,ProductEvent.event_name==name).limit(1))
    if not exists: db.add(ProductEvent(organization_id=user.organization_id,user_id=user.id,event_name=name,source=source,metadata_json=metadata))

def sync_milestones(db:Session,user:User)->dict:
    patient_at=db.scalar(select(func.min(Patient.created_at)).where(Patient.organization_id==user.organization_id))
    schedule_at=db.scalar(select(func.min(Visit.created_at)).where(Visit.organization_id==user.organization_id))
    record_at=db.scalar(select(func.min(ServiceRecord.created_at)).where(ServiceRecord.organization_id==user.organization_id))
    changed=False
    for field,value,name in (("first_patient_at",patient_at,"first_patient_created"),("first_schedule_at",schedule_at,"first_schedule_created"),("first_record_at",record_at,"first_attendance_record_created")):
        if value and not getattr(user,field): setattr(user,field,value);event(db,user,name);changed=True
    if patient_at and schedule_at and record_at and not user.activated_at:
        user.activated_at=max(patient_at,schedule_at,record_at);event(db,user,"user_activated");changed=True
    flags={
        "email":bool(user.email_verified_at),
        "profile":bool(user.professional_summary and user.profession and user.phone),
        "patient":bool(patient_at),"schedule":bool(schedule_at),"record":bool(record_at),
        "pdf":bool(db.scalar(select(ProductEvent.id).where(ProductEvent.user_id==user.id,ProductEvent.event_name=="first_pdf_generated"))),
        "ai":bool(db.scalar(select(AIAnalysis.id).where(AIAnalysis.organization_id==user.organization_id).limit(1))),
        "finance":bool(db.scalar(select(FinanceEntry.id).where(FinanceEntry.organization_id==user.organization_id).limit(1))),
        "availability":bool(db.scalar(select(ProfessionalAvailability.id).where(ProfessionalAvailability.professional_id==user.id).limit(1))),
        "family":bool(db.scalar(select(Responsible.id).where(Responsible.organization_id==user.organization_id,Responsible.portal_user_id.is_not(None)).limit(1))),
    }
    event_names={"email":"email_confirmed","profile":"profile_completed","patient":"first_patient_created","schedule":"first_schedule_created","record":"first_attendance_record_created","pdf":"first_pdf_generated","ai":"first_ai_use","finance":"first_financial_entry","availability":"availability_configured","family":"family_portal_accessed"}
    for code,completed in flags.items():
        if completed:event(db,user,event_names[code])
    if changed: db.flush()
    return flags

def status(db:Session,user:User)->dict:
    flags=sync_milestones(db,user);events={row.event_name:row.created_at for row in db.scalars(select(ProductEvent).where(ProductEvent.user_id==user.id)).all()}
    items=[]
    event_names={"email":"email_confirmed","profile":"profile_completed","patient":"first_patient_created","schedule":"first_schedule_created","record":"first_attendance_record_created","pdf":"first_pdf_generated","ai":"first_ai_use","finance":"first_financial_entry","availability":"availability_configured","family":"family_portal_accessed"}
    for code,title,benefit,path in STEPS:
        completed=flags[code];items.append({"code":code,"title":title,"benefit":benefit,"action_path":path,"completed":completed,"completed_at":events.get(event_names[code])})
    completed=sum(1 for item in items if item["completed"]);next_item=next((item for item in items if not item["completed"]),None)
    return {"progress":completed*10,"completed_steps":completed,"total_steps":10,"activated":bool(user.activated_at),"activated_at":user.activated_at,"days_to_activation":(user.activated_at.date()-user.created_at.date()).days if user.activated_at else None,"steps":items,"next_action":next_item}
