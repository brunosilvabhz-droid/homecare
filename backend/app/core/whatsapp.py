import re
import httpx
from app.core.config import settings

def configured()->bool: return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)
def normalize_phone(value:str)->str:
    digits=re.sub(r"\D","",value or "")
    return digits if digits.startswith("55") else f"55{digits}"
def send_confirmation(phone:str,patient_name:str,date_text:str,time_text:str,url:str)->str:
    if not configured(): raise RuntimeError("WhatsApp Business não configurado")
    parameters=[{"type":"text","text":patient_name},{"type":"text","text":date_text},{"type":"text","text":time_text},{"type":"text","text":url}]
    payload={"messaging_product":"whatsapp","to":normalize_phone(phone),"type":"template","template":{"name":settings.whatsapp_confirmation_template,"language":{"code":settings.whatsapp_template_language},"components":[{"type":"body","parameters":parameters}]}}
    response=httpx.post(f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages",json=payload,headers={"Authorization":f"Bearer {settings.whatsapp_access_token}"},timeout=30)
    response.raise_for_status();return response.json()["messages"][0]["id"]
