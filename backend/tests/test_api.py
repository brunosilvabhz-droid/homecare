import os
from datetime import datetime
from zoneinfo import ZoneInfo
os.environ["DATABASE_URL"]="sqlite:///./test_impactocare.db"
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.db.session import SessionLocal
from app.models import User, Responsible
from app.core.security import create_email_token
client=TestClient(app)
def setup_module(): Base.metadata.create_all(engine)
def teardown_module(): Base.metadata.drop_all(engine)
def test_health(): assert client.get("/health").json()=={"status":"ok"}
def test_tenant_flow(monkeypatch):
    payload={"name":"Ana Souza","email":"ana@example.com","password":"segura123","organization_name":"Ana Cuidados","phone":"31999999999","cpf":"52998224725","profession":"nurse","council_name":"COREN","council_code":"123456","council_state":"MG","city":"Belo Horizonte","state":"MG","accept_lgpd":True}
    registered=client.post("/api/v1/auth/register",json=payload)
    assert registered.status_code==201
    assert client.post("/api/v1/auth/login",json={"email":payload["email"],"password":payload["password"]}).status_code==403
    with SessionLocal() as db: user=db.query(User).filter(User.email==payload["email"]).one(); verification=create_email_token(user.id)
    assert client.get("/api/v1/auth/verify-email",params={"token":verification}).status_code==200
    token=client.post("/api/v1/auth/login",json={"email":payload["email"],"password":payload["password"]}).json()["access_token"]; headers={"Authorization":f"Bearer {token}"}
    patient=client.post("/api/v1/patients",json={"name":"Maria","phone":"31999999999","email":"maria@example.com","address":"Praça Sete","city":"Belo Horizonte","state":"MG","responsible":{"name":"Carlos","relationship":"Filho","phone":"31988888888"}},headers=headers)
    assert patient.status_code==201
    assert client.get("/api/v1/patients",headers=headers).json()[0]["name"]=="Maria"
    with SessionLocal() as db: assert db.query(Responsible).filter(Responsible.name=="Carlos").count()==1
    visit=client.post("/api/v1/visits",json={"patient_id":patient.json()["id"],"starts_at":datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),"duration_minutes":60},headers=headers)
    assert visit.status_code==201
    vehicle=client.post("/api/v1/vehicles",json={"name":"Carro","average_km_per_liter":"10","fuel_price":"6","additional_cost_per_km":"0.10","is_default":True},headers=headers)
    assert vehicle.status_code==201
    monkeypatch.setattr("app.api.geocode",lambda address:(-19.92,-43.94))
    monkeypatch.setattr("app.api.calculate_route",lambda points,roundtrip,optimize:{"order":[0,1],"route":{"distance":20000,"duration":1800,"legs":[{"distance":10000,"duration":900},{"distance":10000,"duration":900}],"geometry":{"type":"LineString","coordinates":[[-43.94,-19.92],[-43.93,-19.91]]}}})
    route=client.post("/api/v1/routes/calculate",json={"date":datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat(),"vehicle_id":vehicle.json()["id"],"start_address":"Belo Horizonte, MG","return_to_start":True,"optimize_order":True},headers=headers)
    assert route.status_code==200 and route.json()["total_distance_km"]==20.0
    subscription=client.get("/api/v1/billing/subscription",headers=headers)
    assert subscription.status_code==200 and subscription.json()["status"]=="trial"
