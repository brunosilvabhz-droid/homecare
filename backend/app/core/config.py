from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Impacto Care"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./impactocare.db"
    jwt_secret: str = "dev-secret-change-me-with-32-characters"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    frontend_url: str = "http://localhost:5173"
    email_verification_expire_hours: int = 24
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "nao-responda@impactocg.com"
    smtp_use_tls: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def origins(self): return [x.strip() for x in self.cors_origins.split(",")]

@lru_cache
def get_settings(): return Settings()
settings = get_settings()
