from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import router
app=FastAPI(title=settings.app_name,version="0.1.0",docs_url="/docs")
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router,prefix=settings.api_prefix)
@app.get("/health")
def health(): return {"status":"ok"}
