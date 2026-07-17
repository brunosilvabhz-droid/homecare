"""Creates and removes the isolated media/demo account.

Create:   DEMO_USER_PASSWORD='strong-password' python -m app.demo_seed
Rollback: python -m app.demo_seed --rollback
"""
from __future__ import annotations

import argparse
import hashlib
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal
from app.models import (
    AIAnalysis, BillingCycle, FinanceEntry, Organization, Patient, Plan,
    ProfessionalAvailability, Responsible, Role, ServiceRecord, Subscription,
    SubscriptionReminder, SubscriptionStatus, User, Vehicle, Visit, VisitStatus,
    WhatsAppConfirmation, GoogleIdentity,
)

DEMO_EMAIL=os.getenv("DEMO_USER_EMAIL","demo.fisioterapia@impactocg.com").lower()
DEMO_ORGANIZATION="Impacto Care — Demonstração Fisioterapia"

PATIENTS=[
    {"name":"Maria Aparecida Oliveira","birth_date":date(1948,3,12),"phone":"31988881001","address":"Rua dos Timbiras","address_number":"1240","neighborhood":"Funcionários","postal_code":"30140061","conditions":"Hipertensão controlada; recuperação pós-operatória de joelho","medications":"Losartana conforme orientação informada pela família","allergies":"Sem alergias informadas","care_needs":"Fortalecimento, mobilidade e treino de marcha","mobility":"Utiliza bengala em trajetos longos","session_value":Decimal("150.00")},
    {"name":"João Carlos Mendes","birth_date":date(1955,8,27),"phone":"31988881002","address":"Avenida do Contorno","address_number":"3280","neighborhood":"Santa Efigênia","postal_code":"30110017","conditions":"Histórico de AVC; diabetes informada","medications":"Metformina e medicação contínua informadas pelo responsável","allergies":"Dipirona","care_needs":"Equilíbrio, transferências e condicionamento funcional","mobility":"Caminha com apoio de familiar","session_value":Decimal("170.00")},
    {"name":"Ana Laura Ferreira","birth_date":date(1963,11,4),"phone":"31988881003","address":"Rua Pium-í","address_number":"780","neighborhood":"Sion","postal_code":"30310220","conditions":"Dor lombar recorrente","medications":"Analgésico eventual informado pela paciente","allergies":"Sem alergias informadas","care_needs":"Mobilidade, educação postural e exercícios domiciliares","mobility":"Independente","session_value":Decimal("140.00")},
    {"name":"Carlos Eduardo Silva","birth_date":date(1971,6,19),"phone":"31988881004","address":"Rua Padre Eustáquio","address_number":"1750","neighborhood":"Padre Eustáquio","postal_code":"30720100","conditions":"Recuperação de lesão no ombro direito","medications":"Anti-inflamatório anteriormente informado","allergies":"Sem alergias informadas","care_needs":"Amplitude de movimento e fortalecimento progressivo","mobility":"Independente","session_value":Decimal("160.00")},
]

def local_at(days:int,hour:int,minute:int=0)->datetime:
    current=datetime.now(timezone.utc).astimezone()
    return (current+timedelta(days=days)).replace(hour=hour,minute=minute,second=0,microsecond=0).astimezone(timezone.utc)

def rollback(db)->bool:
    org=db.scalar(select(Organization).where(Organization.name==DEMO_ORGANIZATION))
    if not org:
        print("Conta de demonstração não encontrada; nada foi removido.")
        return False
    user_ids=list(db.scalars(select(User.id).where(User.organization_id==org.id)))
    subscription_ids=list(db.scalars(select(Subscription.id).where(Subscription.organization_id==org.id)))
    if user_ids:
        db.execute(delete(GoogleIdentity).where(GoogleIdentity.user_id.in_(user_ids)))
    if subscription_ids:
        db.execute(delete(SubscriptionReminder).where(SubscriptionReminder.subscription_id.in_(subscription_ids)))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name=="organizations":
            continue
        if "organization_id" in table.c:
            db.execute(table.delete().where(table.c.organization_id==org.id))
    db.delete(org)
    db.commit()
    print(f"Rollback concluído: {DEMO_ORGANIZATION} removida.")
    return True

def create(db,password:str):
    existing=db.scalar(select(User).where(User.email==DEMO_EMAIL))
    if existing:
        print(f"Conta demo já existe: {DEMO_EMAIL}. Nenhuma duplicação foi criada.")
        return
    now=datetime.now(timezone.utc)
    org=Organization(name=DEMO_ORGANIZATION);db.add(org);db.flush()
    user=User(organization_id=org.id,name="Bruno Henrique da Silva — Demo",email=DEMO_EMAIL,password_hash=hash_password(password),role=Role.PROFESSIONAL,is_active=True,email_verified_at=now,last_login_at=now,phone="31988889999",cpf="07043585651",profession="Fisioterapeuta",council_name="CREFITO",council_code="123456-F",council_state="MG",postal_code="30140071",address="Avenida Brasil",address_number="1200",neighborhood="Funcionários",city="Belo Horizonte",state="MG",default_session_duration_minutes=60,professional_summary="Fisioterapeuta com atuação em atendimento domiciliar, reabilitação funcional e acompanhamento de pessoas idosas.",specialties="Fisioterapia geriátrica; ortopedia; reabilitação funcional; prevenção de quedas",education="Graduação em Fisioterapia; formação complementar em saúde da pessoa idosa",experience_years=9,service_areas="Belo Horizonte — Centro-Sul, Noroeste e região hospitalar",professional_approach="Atendimento individualizado com objetivos funcionais definidos em conjunto com o paciente e a família.",signature_name="Bruno Henrique da Silva",signature_council="CREFITO 123456-F / MG",signature_profession="Fisioterapeuta",registration_source="demo_seed",first_access_at=now-timedelta(days=120),first_patient_at=now-timedelta(days=118),first_schedule_at=now-timedelta(days=116),first_record_at=now-timedelta(days=114),activated_at=now-timedelta(days=110),whatsapp_allowed=True,communication_consent_at=now-timedelta(days=120),communication_consent_source="demo_seed",communication_consent_version="1.0")
    db.add(user);db.flush()
    plan=db.scalar(select(Plan).where(Plan.code=="premium"))
    if not plan:
        plan=Plan(code="premium",name="Impacto Care Premium",monthly_price=Decimal("79.90"),annual_monthly_price=Decimal("59.90"),ai_daily_limit=20,whatsapp_monthly_limit=100);db.add(plan);db.flush()
    db.add(Subscription(organization_id=org.id,plan_id=plan.id,status=SubscriptionStatus.ACTIVE,billing_cycle=BillingCycle.ANNUAL,current_period_end=(now+timedelta(days=365)).date(),complimentary_until=(now+timedelta(days=365)).date(),complimentary_note="Conta exclusiva para demonstração e produção de mídia"))
    db.add(Vehicle(organization_id=org.id,name="Veículo de demonstração",fuel_type="gasoline",average_km_per_liter=Decimal("11.50"),fuel_price=Decimal("6.09"),additional_cost_per_km=Decimal("0.18"),is_default=True))
    for weekday in range(5):db.add(ProfessionalAvailability(organization_id=org.id,professional_id=user.id,weekday=weekday,start_time=time(8),end_time=time(18),is_active=True))
    patients=[]
    for index,data in enumerate(PATIENTS):
        patient=Patient(organization_id=org.id,status="active",cpf=f"00000000{index+101:03d}",gender="Não informado",email=f"familia.demo{index+1}@example.com",city="Belo Horizonte",state="MG",latitude=-19.92-(index*.006),longitude=-43.94-(index*.005),session_count=12,notes="Dados fictícios criados exclusivamente para demonstração.",**data)
        db.add(patient);db.flush();patients.append(patient)
        db.add(Responsible(organization_id=org.id,patient_id=patient.id,name=["Fernanda Oliveira","Mariana Mendes","Paulo Ferreira","Renata Silva"][index],relationship=["Filha","Filha","Filho","Esposa"][index],phone=f"3197777200{index+1}",email=f"responsavel.demo{index+1}@example.com"))
    schedule=[(-42,9,0),(-35,14,0),(-28,10,30),(-21,15,0),(-14,9,0),(-7,13,30),(-3,10,0),(1,9,0),(2,11,0),(3,14,30),(5,8,30),(7,15,0),(9,10,0),(12,13,30),(15,9,30),(18,16,0)]
    visits=[]
    for index,(days,hour,minute) in enumerate(schedule):
        patient=patients[index%len(patients)];past=days<0
        token=f"demo-visit-{index}-{org.id}"
        visit=Visit(organization_id=org.id,patient_id=patient.id,professional_id=user.id,starts_at=local_at(days,hour,minute),duration_minutes=60,status=VisitStatus.COMPLETED if past else VisitStatus.SCHEDULED,notes="Atendimento domiciliar de demonstração.",confirmation_token_hash=hashlib.sha256(token.encode()).hexdigest(),confirmation_manual_sent_at=local_at(days-1,hour) if not past and index%2==0 else None,patient_response="confirmed" if (past or index%3!=0) else None,patient_responded_at=local_at(days-1,hour+1) if not past and index%3!=0 else None)
        db.add(visit);db.flush();visits.append(visit)
        if not past:
            db.add(WhatsAppConfirmation(organization_id=org.id,visit_id=visit.id,status="sent" if visit.confirmation_manual_sent_at else "pending",attempts=1 if visit.confirmation_manual_sent_at else 0,sent_at=visit.confirmation_manual_sent_at))
        amount=patient.session_value
        db.add(FinanceEntry(organization_id=org.id,patient_id=patient.id,entry_type="income",category="Atendimento domiciliar",source="demo_seed",description=f"Sessão — {patient.name}",amount=amount,due_date=visit.starts_at.date(),paid=past))
        if past:
            summaries=["Paciente apresentou boa participação. Realizados exercícios de mobilidade e fortalecimento com tolerância adequada.","Treino funcional realizado com foco em equilíbrio, transferências e segurança no ambiente domiciliar.","Evolução compatível com os objetivos definidos. Mantidas orientações de exercícios entre as visitas."]
            record=ServiceRecord(organization_id=org.id,patient_id=patient.id,visit_id=visit.id,professional_id=user.id,occurred_at=visit.starts_at+timedelta(minutes=55),summary=summaries[index%3],guidance="Manter exercícios orientados, respeitar sinais de fadiga e comunicar alterações relevantes ao profissional.",weight_kg=Decimal(str(62+index)),blood_pressure_systolic=120+(index%3)*5,blood_pressure_diastolic=80,heart_rate_bpm=72+(index%5),respiratory_rate_bpm=16,temperature_c=Decimal("36.5"),oxygen_saturation_percent=97,responsible_name="Responsável presente",professional_signature_name=user.signature_name,professional_signature_council=user.signature_council,professional_signature_profession=user.signature_profession)
            db.add(record)
    expenses=[("Combustível",Decimal("286.40"),-25),("Estacionamento",Decimal("96.00"),-18),("Materiais",Decimal("178.90"),-12),("Internet e telefone",Decimal("119.90"),-5),("Combustível",Decimal("210.00"),5)]
    for category,amount,days in expenses:db.add(FinanceEntry(organization_id=org.id,entry_type="expense",category=category,source="demo_seed",description=f"{category} — operação",amount=amount,due_date=date.today()+timedelta(days=days),paid=days<0))
    for visit in visits[-4:-2]:
        db.add(AIAnalysis(organization_id=org.id,visit_id=visit.id,patient_id=visit.patient_id,professional_id=user.id,analysis_type="preparation",content={"summary":"Resumo demonstrativo baseado no histórico registrado.","attention_points":["Revisar evolução funcional","Confirmar adesão às orientações"],"suggested_questions":["Como se sentiu desde a última visita?"],"next_actions":["Reavaliar objetivos funcionais"],"safety_note":"Conteúdo de apoio sujeito à revisão profissional."},model="demo-data",input_tokens=0,output_tokens=0))
    db.commit()
    print("Carga de demonstração concluída.")
    print(f"Login: {DEMO_EMAIL}")
    print("Senha: valor informado em DEMO_USER_PASSWORD")
    print(f"Organização: {DEMO_ORGANIZATION}")

def main():
    parser=argparse.ArgumentParser(description="Gerencia a conta de demonstração da Impacto Care")
    parser.add_argument("--rollback",action="store_true",help="Remove integralmente a organização demo")
    args=parser.parse_args();db=SessionLocal()
    try:
        if args.rollback:rollback(db)
        else:
            password=os.getenv("DEMO_USER_PASSWORD")
            if not password or len(password)<12:raise SystemExit("Defina DEMO_USER_PASSWORD com pelo menos 12 caracteres.")
            create(db,password)
    except Exception:
        db.rollback();raise
    finally:db.close()

if __name__=="__main__":main()
