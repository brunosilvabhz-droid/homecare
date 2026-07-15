import os
os.environ["DATABASE_URL"]="sqlite:///./test_impactocare.db"
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine
from app.main import app
client=TestClient(app)
def setup_module(): Base.metadata.create_all(engine)
def teardown_module(): Base.metadata.drop_all(engine)
def test_health(): assert client.get("/health").json()=={"status":"ok"}
def test_tenant_flow():
    payload={"name":"Ana","email":"ana@example.com","password":"segura123","organization_name":"Ana Cuidados","accept_lgpd":True}
    token=client.post("/api/v1/auth/register",json=payload).json()["access_token"]; headers={"Authorization":f"Bearer {token}"}
    patient=client.post("/api/v1/patients",json={"name":"Maria","phone":"11999999999"},headers=headers)
    assert patient.status_code==201
    assert client.get("/api/v1/patients",headers=headers).json()[0]["name"]=="Maria"
    subscription=client.get("/api/v1/billing/subscription",headers=headers)
    assert subscription.status_code==200 and subscription.json()["status"]=="trial"
