from functools import lru_cache
import os
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
    support_email: str = "contato@impactocg.com"
    smtp_use_tls: bool = True
    google_client_id: str | None = None
    turnstile_secret_key: str | None = None
    geocoder_url: str = "https://nominatim.openstreetmap.org"
    routing_url: str = "https://router.project-osrm.org"
    map_user_agent: str = "ImpactoCare/0.1 contato@impactocg.com"
    asaas_api_url: str = "https://api-sandbox.asaas.com/v3"
    asaas_api_key: str | None = None
    asaas_checkout_url: str = "https://sandbox.asaas.com/checkoutSession/show"
    asaas_webhook_token: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str = "v23.0"
    whatsapp_confirmation_template: str = "impacto_care_confirmacao_24h"
    whatsapp_template_language: str = "pt_BR"
    automation_interval_seconds: int = 300
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def origins(self): return [x.strip() for x in self.cors_origins.split(",")]
    @property
    def google_oauth_client_id(self): return self.google_client_id or os.getenv("VITE_GOOGLE_CLIENT_ID")

@lru_cache
def get_settings(): return Settings()
settings = get_settings()
