import os
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Organization, User, Role
from app.core.security import hash_password
def main():
    email=os.getenv("ADMIN_EMAIL","admin@homecarepro.local").lower(); password=os.getenv("ADMIN_PASSWORD","ChangeMe123!")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email==email)): return
        org=Organization(name="HomeCare Pro Admin"); db.add(org); db.flush(); db.add(User(name="Administrador",email=email,password_hash=hash_password(password),role=Role.ADMIN,organization_id=org.id)); db.commit()
if __name__=="__main__": main()
