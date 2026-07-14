from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

kwargs = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
