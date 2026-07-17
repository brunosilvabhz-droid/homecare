import json
import httpx
from fastapi import HTTPException
from app.core.config import settings

SCHEMA={"type":"object","additionalProperties":False,"properties":{"summary":{"type":"string"},"attention_points":{"type":"array","items":{"type":"string"}},"suggested_questions":{"type":"array","items":{"type":"string"}},"next_actions":{"type":"array","items":{"type":"string"}},"safety_note":{"type":"string"}},"required":["summary","attention_points","suggested_questions","next_actions","safety_note"]}

def generate_analysis(kind:str,context:dict)->tuple[dict,dict]:
    if not settings.openai_api_key: raise HTTPException(503,"Assistente de IA ainda não configurado")
    purpose="preparação objetiva para a próxima visita" if kind=="preparation" else "síntese da evolução observada no atendimento"
    instructions=("Você auxilia um profissional de atendimento domiciliar a organizar informações. "
        "Não diagnostique, não prescreva, não altere medicamentos e não afirme causalidade. "
        "Use somente os dados fornecidos, destaque incertezas e gere um rascunho que exige revisão humana. "
        f"Produza uma {purpose}.")
    payload={"model":settings.openai_model,"store":False,"instructions":instructions,"input":json.dumps(context,ensure_ascii=False),"text":{"format":{"type":"json_schema","name":"care_assistance","strict":True,"schema":SCHEMA}}}
    try:
        response=httpx.post("https://api.openai.com/v1/responses",json=payload,headers={"Authorization":f"Bearer {settings.openai_api_key}","Content-Type":"application/json"},timeout=60)
        response.raise_for_status();body=response.json();text=body.get("output_text")
        if not text: text=next((part.get("text") for item in body.get("output",[]) for part in item.get("content",[]) if part.get("type")=="output_text"),None)
        if not text: raise ValueError("Resposta sem conteúdo")
        return json.loads(text),body.get("usage") or {}
    except httpx.HTTPStatusError as error: raise HTTPException(502,"Não foi possível gerar a análise de IA") from error
    except (httpx.HTTPError,ValueError,json.JSONDecodeError) as error: raise HTTPException(502,"Assistente de IA indisponível no momento") from error
