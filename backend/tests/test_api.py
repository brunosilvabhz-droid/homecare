import os
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
os.environ["DATABASE_URL"]="sqlite:///./test_impactocare.db"
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.db.session import SessionLocal
from app.models import User, Organization, Role, Responsible, Subscription, SubscriptionStatus, BillingCycle, Plan, WhatsAppConfirmation
from app.core.security import create_email_token, create_password_reset_token, create_token, hash_password
from app.core.subscriptions import subscription_access
from app.subscription_reminders import run as run_subscription_reminders
from app.automation_worker import run_once as run_whatsapp_automation
from app.relationship_automation import run_once as run_relationship_automation
client=TestClient(app)
def setup_module(): Base.metadata.create_all(engine)
def teardown_module(): Base.metadata.drop_all(engine)
def test_health(): assert client.get("/health").json()=={"status":"ok"}
def test_subscription_access_policy():
    today=datetime.now().date()
    trial=Subscription(status=SubscriptionStatus.TRIAL,billing_cycle=BillingCycle.MONTHLY,current_period_end=today)
    assert subscription_access(trial,today)["blocked"] is False
    trial.current_period_end=today-timedelta(days=1)
    assert subscription_access(trial,today)["blocked"] is True
    monthly=Subscription(status=SubscriptionStatus.ACTIVE,billing_cycle=BillingCycle.MONTHLY,current_period_end=today-timedelta(days=5))
    assert subscription_access(monthly,today)["phase"]=="grace"
    monthly.current_period_end=today-timedelta(days=6)
    assert subscription_access(monthly,today)["blocked"] is True
def test_tenant_flow(monkeypatch):
    payload={"name":"Ana Souza","email":"ana@example.com","password":"segura123","organization_name":"Ana Cuidados","phone":"31999999999","cpf":"52998224725","profession":"nurse","council_name":"COREN","council_code":"123456","council_state":"MG","city":"Belo Horizonte","state":"MG","accept_lgpd":True}
    registered=client.post("/api/v1/auth/register",json=payload)
    assert registered.status_code==201
    assert client.post("/api/v1/auth/login",json={"email":payload["email"],"password":payload["password"]}).status_code==403
    with SessionLocal() as db: user=db.query(User).filter(User.email==payload["email"]).one(); verification=create_email_token(user.id)
    assert client.get("/api/v1/auth/verify-email",params={"token":verification}).status_code==200
    reset=create_password_reset_token(user.id)
    assert client.post("/api/v1/auth/reset-password",json={"token":reset,"password":"novaSenha123"}).status_code==200
    payload["password"]="novaSenha123"
    token=client.post("/api/v1/auth/login",json={"email":payload["email"],"password":payload["password"]}).json()["access_token"]; headers={"Authorization":f"Bearer {token}"}
    with SessionLocal() as db:
        account=db.query(User).filter(User.email==payload["email"]).one(); assert account.last_login_at is not None
        admin_org=Organization(name="Impacto Care Admin Test"); db.add(admin_org); db.flush()
        admin_user=User(organization_id=admin_org.id,name="Administrador Geral",email="admin-geral@example.com",password_hash=hash_password("AdminSegura123"),role=Role.ADMIN,email_verified_at=datetime.now(ZoneInfo("America/Sao_Paulo"))); db.add(admin_user); db.commit(); admin_id=admin_user.id
    assert client.get("/api/v1/admin/users",headers=headers).status_code==403
    admin_headers={"Authorization":f"Bearer {create_token(admin_id)}"}; admin_users=client.get("/api/v1/admin/users",headers=admin_headers)
    assert admin_users.status_code==200 and any(item["email"]==payload["email"] and item["last_login_at"] for item in admin_users.json())
    monkeypatch.setattr("app.api.settings.google_client_id","google-client-test")
    monkeypatch.setattr("app.api.google_id_token.verify_oauth2_token",lambda credential,request,audience:{"sub":"google-ana-1","email":payload["email"],"email_verified":True,"name":"Ana Souza"})
    google_login=client.post("/api/v1/auth/google",json={"credential":"valid-google-token"})
    assert google_login.status_code==200 and google_login.json()["access_token"]
    monkeypatch.setattr("app.api.google_id_token.verify_oauth2_token",lambda credential,request,audience:{"sub":"google-bruno-2","email":"bruno.google@example.com","email_verified":True,"name":"Bruno Google"})
    google_register=client.post("/api/v1/auth/google",json={"credential":"new-google-token","organization_name":"Bruno Cuidados","phone":"31988887777","cpf":"52998224725","profession":"nurse","council_name":"COREN","council_state":"MG","city":"Belo Horizonte","state":"MG","accept_lgpd":True})
    assert google_register.status_code==200 and google_register.json()["access_token"]
    monkeypatch.setattr("app.api.send_support_ticket_email",lambda *args:True)
    ticket=client.post("/api/v1/support/tickets",json={"category":"error","description":"A agenda não carregou durante o teste."},headers=headers)
    assert ticket.status_code==201 and ticket.json()["ticket_number"].startswith("ICP-") and ticket.json()["email_sent_at"]
    assert client.get("/api/v1/support/tickets",headers=headers).json()[0]["ticket_number"]==ticket.json()["ticket_number"]
    admin_ticket=client.get("/api/v1/admin/support/tickets",headers=admin_headers).json()[0]
    assert admin_ticket["requester_name"]==payload["name"] and admin_ticket["requester_email"]==payload["email"] and admin_ticket["description"]
    patient=client.post("/api/v1/patients",json={"name":"Maria","phone":"31999999999","email":"maria@example.com","address":"Praça Sete","city":"Belo Horizonte","state":"MG","responsible":{"name":"Carlos","relationship":"Filho","phone":"31988888888"}},headers=headers)
    assert patient.status_code==201
    assert client.get("/api/v1/patients",headers=headers).json()[0]["name"]=="Maria"
    with SessionLocal() as db: assert db.query(Responsible).filter(Responsible.name=="Carlos").count()==1
    visit=client.post("/api/v1/visits",json={"patient_id":patient.json()["id"],"starts_at":datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),"duration_minutes":60},headers=headers)
    target=(datetime.now(ZoneInfo("America/Sao_Paulo"))+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
    availability=client.put("/api/v1/availability",json={"default_session_duration_minutes":45,"windows":[{"weekday":target.weekday(),"start_time":"08:00","end_time":"18:00","is_active":True}]},headers=headers)
    assert availability.status_code==200 and availability.json()["default_session_duration_minutes"]==45
    confirmation=client.post(f"/api/v1/visits/{visit.json()['id']}/confirmation-link",headers=headers)
    assert confirmation.status_code==200
    assert client.get("/api/v1/visits",headers=headers).json()[0]["confirmation_manual_sent_at"]
    confirmation_token=confirmation.json()["url"].rsplit("/",1)[-1]
    assert client.post(f"/api/v1/public/visits/{confirmation_token}/response",json={"action":"confirm"}).json()["patient_response"]=="confirmed"
    slots=client.get(f"/api/v1/public/visits/{confirmation_token}/available-slots",params={"date_from":target.date().isoformat(),"date_to":target.date().isoformat()})
    assert slots.status_code==200 and slots.json()
    professional_slots=client.get("/api/v1/availability/free-slots",params={"date_from":target.date().isoformat(),"date_to":target.date().isoformat()},headers=headers)
    assert professional_slots.status_code==200 and professional_slots.json()
    monkeypatch.setattr("app.api.send_visit_change_email",lambda *args:True)
    changed=client.post(f"/api/v1/public/visits/{confirmation_token}/response",json={"action":"reschedule","new_starts_at":slots.json()[0]["starts_at"]})
    assert changed.status_code==200 and changed.json()["patient_response"]=="rescheduled" and changed.json()["duration_minutes"]==45
    record=client.post("/api/v1/records",json={"patient_id":patient.json()["id"],"visit_id":visit.json()["id"],"summary":"Paciente estável.","weight_kg":"72.5","blood_pressure_systolic":120,"blood_pressure_diastolic":80,"heart_rate_bpm":72,"temperature_c":"36.5","oxygen_saturation_percent":98},headers=headers)
    assert record.status_code==201 and record.json()["weight_kg"]=="72.50" and record.json()["oxygen_saturation_percent"]==98
    onboarding=client.get("/api/v1/onboarding",headers=headers)
    assert onboarding.status_code==200 and onboarding.json()["activated"] is True
    assert onboarding.json()["completed_steps"]>=5 and onboarding.json()["progress"]>=50
    assert next(step for step in onboarding.json()["steps"] if step["code"]=="patient")["completed"] is True
    preferences=client.put("/api/v1/me/communications",json={"email_operational":True,"email_guidance":True,"email_billing":True,"email_marketing":False,"whatsapp_allowed":True},headers=headers)
    assert preferences.status_code==200 and preferences.json()["whatsapp_allowed"] is True
    ai_content={"summary":"Resumo revisável","attention_points":["Observar evolução"],"suggested_questions":["Houve mudanças?"],"next_actions":["Revisar orientações"],"safety_note":"Revisão profissional obrigatória."}
    monkeypatch.setattr("app.api.generate_analysis",lambda kind,context:(ai_content,{"input_tokens":100,"output_tokens":50}))
    preparation=client.post(f"/api/v1/visits/{visit.json()['id']}/ai-analysis",json={"analysis_type":"preparation"},headers=headers)
    evolution=client.post(f"/api/v1/visits/{visit.json()['id']}/ai-analysis",json={"analysis_type":"evolution"},headers=headers)
    assert preparation.status_code==200 and evolution.status_code==200
    repeated=client.post(f"/api/v1/visits/{visit.json()['id']}/ai-analysis",json={"analysis_type":"preparation"},headers=headers)
    assert repeated.json()["id"]==preparation.json()["id"]
    assert visit.status_code==201
    assert client.post(f"/api/v1/visits/{visit.json()['id']}/cancel",headers=headers).json()["status"]=="canceled"
    visit=client.post("/api/v1/visits",json={"patient_id":patient.json()["id"],"starts_at":datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),"duration_minutes":60},headers=headers)
    update={**patient.json(),"session_value":"120.00","session_count":3,"conditions":"Hipertensão","responsible":None}
    assert client.patch(f"/api/v1/patients/{patient.json()['id']}",json=update,headers=headers).status_code==200
    automatic=[x for x in client.get("/api/v1/finance",headers=headers).json() if x.get("source")=="patient_sessions"]
    assert len(automatic)==3 and all(x["amount"]=="120.00" for x in automatic)
    expense=client.post("/api/v1/finance",json={"entry_type":"expense","category":"Combustível","description":"Combustível","amount":"50.00","due_date":datetime.now().date().isoformat(),"paid":True},headers=headers)
    assert expense.status_code==201 and expense.json()["entry_type"]=="expense" and expense.json()["category"]=="Combustível"
    chart=client.get("/api/v1/dashboard/finance-chart",params={"days":120},headers=headers)
    assert chart.status_code==200 and any(Decimal(x["expenses"])>0 for x in chart.json())
    vehicle=client.post("/api/v1/vehicles",json={"name":"Carro","average_km_per_liter":"10","fuel_price":"6","additional_cost_per_km":"0.10","is_default":True},headers=headers)
    assert vehicle.status_code==201
    monkeypatch.setattr("app.api.geocode",lambda address:(-19.92,-43.94))
    monkeypatch.setattr("app.api.calculate_route",lambda points,roundtrip,optimize:{"order":[0,1],"route":{"distance":20000,"duration":1800,"legs":[{"distance":10000,"duration":900},{"distance":10000,"duration":900}],"geometry":{"type":"LineString","coordinates":[[-43.94,-19.92],[-43.93,-19.91]]}}})
    route=client.post("/api/v1/routes/calculate",json={"date":datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat(),"vehicle_id":vehicle.json()["id"],"start_address":"Belo Horizonte, MG","return_to_start":True,"optimize_order":True},headers=headers)
    assert route.status_code==200 and route.json()["total_distance_km"]==20.0
    direct_route=client.post("/api/v1/routes/calculate",json={"date":datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat(),"average_km_per_liter":"10","fuel_price":"6","start_address":"Belo Horizonte, MG"},headers=headers)
    assert direct_route.status_code==200
    intake_link=client.post("/api/v1/intakes",json={"expires_in_days":7,"recipient_name":"José","recipient_phone":"31999990000"},headers=headers)
    assert intake_link.status_code==201
    intake_token=intake_link.json()["url"].rsplit("/",1)[-1]
    assert client.get(f"/api/v1/public/intakes/{intake_token}").status_code==200
    submitted=client.post(f"/api/v1/public/intakes/{intake_token}",json={"patient_name":"Zilda Souza","birth_date":"1950-01-01","phone":"31977777777","address":"Rua A","city":"Belo Horizonte","state":"MG","conditions":"Hipertensão","medications":"Losartana","needs":"Acompanhamento diário","responsible_name":"José Souza","responsible_relationship":"Filho","responsible_phone":"31966666666","accept_privacy":True})
    assert submitted.status_code==201
    inactive_id=submitted.json()["patient_id"]
    patients=client.get("/api/v1/patients",headers=headers).json()
    assert next(x for x in patients if x["id"]==inactive_id)["status"]=="inactive"
    assert client.post(f"/api/v1/patients/{inactive_id}/activate",headers=headers).status_code==200
    subscription_id=client.get("/api/v1/billing/subscription",headers=headers).json()["id"]
    checkout_payloads=[]
    monkeypatch.setattr("app.api.create_asaas_checkout",lambda payload:checkout_payloads.append(payload) or {"id":"checkout_test_123"})
    checkout=client.post("/api/v1/billing/checkout",json={"billing_cycle":"annual"},headers=headers)
    assert checkout.status_code==200 and "checkout_test_123" in checkout.json()["checkout_url"]
    assert checkout_payloads[-1]["billingTypes"]==["CREDIT_CARD"]
    assert checkout_payloads[-1]["subscription"]["cycle"]=="YEARLY"
    pix_checkout=client.post("/api/v1/billing/checkout",json={"billing_cycle":"monthly","payment_method":"pix"},headers=headers)
    assert pix_checkout.status_code==200
    assert checkout_payloads[-1]["billingTypes"]==["PIX"]
    assert checkout_payloads[-1]["chargeTypes"]==["DETACHED"]
    assert "subscription" not in checkout_payloads[-1]
    monkeypatch.setattr("app.api.settings.asaas_webhook_token","webhook-token-seguro-com-mais-de-32-caracteres")
    event={"id":"evt_test_1","event":"PAYMENT_RECEIVED","payment":{"externalReference":subscription_id,"billingType":"PIX"}}
    webhook=client.post("/api/v1/webhooks/asaas",json=event,headers={"asaas-access-token":"webhook-token-seguro-com-mais-de-32-caracteres"})
    assert webhook.status_code==200
    assert client.get("/api/v1/billing/subscription",headers=headers).json()["status"]=="active"
    duplicate=client.post("/api/v1/webhooks/asaas",json=event,headers={"asaas-access-token":"webhook-token-seguro-com-mais-de-32-caracteres"})
    assert duplicate.json()["duplicate"] is True
    with SessionLocal() as db:
        item=db.get(Subscription,subscription_id);item.status=SubscriptionStatus.TRIAL;item.external_id="checkout_session_pix_1";db.commit()
    checkout_event={"id":"evt_checkout_session_1","event":"PAYMENT_RECEIVED","payment":{"externalReference":None,"checkoutSession":"checkout_session_pix_1","billingType":"PIX"}}
    checkout_webhook=client.post("/api/v1/webhooks/asaas",json=checkout_event,headers={"asaas-access-token":"webhook-token-seguro-com-mais-de-32-caracteres"})
    assert checkout_webhook.status_code==200
    assert client.get("/api/v1/billing/subscription",headers=headers).json()["status"]=="active"
    monkeypatch.setattr("app.api.cancel_asaas_subscription",lambda external_id:(_ for _ in ()).throw(AssertionError("PIX não possui recorrência externa")))
    canceled=client.post("/api/v1/billing/cancel",headers=headers)
    assert canceled.status_code==200 and canceled.json()["cancel_at_period_end"] is True
    assert client.get("/api/v1/billing/subscription",headers=headers).json()["cancel_at_period_end"] is True
    with SessionLocal() as db:
        premium=db.query(Plan).filter(Plan.code=="premium").first()
        if not premium: premium=Plan(code="premium",name="Impacto Care Premium",monthly_price="79.90",annual_monthly_price="59.90",ai_daily_limit=20,whatsapp_monthly_limit=100);db.add(premium);db.flush()
        item=db.get(Subscription,subscription_id);item.plan_id=premium.id;item.status=SubscriptionStatus.ACTIVE;item.cancel_at_period_end=False;db.commit()
    managed=client.patch(f"/api/v1/admin/users/{account.id}",json={"is_active":True,"plan_code":"premium","billing_cycle":"annual","complimentary_days":45,"complimentary_note":"Parceria de avaliação"},headers=admin_headers)
    assert managed.status_code==200
    managed_row=next(x for x in client.get("/api/v1/admin/users",headers=admin_headers).json() if x["id"]==account.id)
    assert managed_row["complimentary_until"] and managed_row["complimentary_note"]=="Parceria de avaliação"
    future=client.post("/api/v1/visits",json={"patient_id":patient.json()["id"],"starts_at":(datetime.now(ZoneInfo("UTC"))+timedelta(hours=12)).isoformat(),"duration_minutes":60},headers=headers)
    monkeypatch.setattr("app.automation_worker.configured",lambda:True);monkeypatch.setattr("app.automation_worker.send_confirmation",lambda *args:"wamid.test")
    automation_now=datetime.now(ZoneInfo("UTC"))
    assert run_whatsapp_automation(automation_now)>=1
    assert run_whatsapp_automation(automation_now)==0
    relationship_now=datetime.now(ZoneInfo("America/Sao_Paulo")).replace(hour=12,minute=0,second=0,microsecond=0).astimezone(ZoneInfo("UTC"))
    monkeypatch.setattr("app.relationship_automation.send_relationship_email",lambda *args:True)
    assert run_relationship_automation(relationship_now)>=1
    assert run_relationship_automation(relationship_now)==0
    with SessionLocal() as db: assert db.query(WhatsAppConfirmation).filter(WhatsAppConfirmation.visit_id==future.json()["id"],WhatsAppConfirmation.status=="sent").count()==1
    period_end=client.get("/api/v1/billing/subscription",headers=headers).json()["current_period_end"]
    card_received={"id":"evt_test_card_received","event":"PAYMENT_RECEIVED","payment":{"externalReference":subscription_id,"billingType":"CREDIT_CARD","subscription":"sub_test_1"}}
    assert client.post("/api/v1/webhooks/asaas",json=card_received,headers={"asaas-access-token":"webhook-token-seguro-com-mais-de-32-caracteres"}).status_code==200
    assert client.get("/api/v1/billing/subscription",headers=headers).json()["current_period_end"]==period_end
    subscription=client.get("/api/v1/billing/subscription",headers=headers)
    assert subscription.status_code==200 and subscription.json()["status"]=="active"
    with SessionLocal() as db:
        item=db.get(Subscription,subscription_id);item.billing_cycle=BillingCycle.MONTHLY;item.cancel_at_period_end=False;item.complimentary_until=None;item.current_period_end=datetime.now().date()-timedelta(days=5);db.commit()
    assert client.get("/api/v1/dashboard",headers=headers).status_code==200
    with SessionLocal() as db:
        item=db.get(Subscription,subscription_id);item.current_period_end=datetime.now().date()-timedelta(days=6);db.commit()
    assert client.get("/api/v1/dashboard",headers=headers).status_code==402
    assert client.get("/api/v1/billing/subscription",headers=headers).status_code==200
    monkeypatch.setattr("app.subscription_reminders.send_plan_expiration_email",lambda *args:True)
    assert run_subscription_reminders(datetime.now().date())==1
    assert run_subscription_reminders(datetime.now().date())==0
