import httpx
from fastapi import HTTPException
from app.core.config import settings

def create_asaas_checkout(payload:dict)->dict:
    if not settings.asaas_api_key: raise HTTPException(503,"Integração ASAAS ainda não configurada")
    try:
        response=httpx.post(f"{settings.asaas_api_url.rstrip('/')}/checkouts",json=payload,headers={"access_token":settings.asaas_api_key,"Content-Type":"application/json"},timeout=65)
        response.raise_for_status(); return response.json()
    except httpx.HTTPStatusError as error:
        detail="Não foi possível criar o checkout"
        try: detail=error.response.json().get("errors",[{}])[0].get("description",detail)
        except (ValueError,IndexError,AttributeError): pass
        raise HTTPException(502,detail) from error
    except (httpx.HTTPError,ValueError) as error: raise HTTPException(502,"ASAAS indisponível no momento") from error
