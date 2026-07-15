from decimal import Decimal, ROUND_HALF_UP
import httpx
from fastapi import HTTPException
from app.core.config import settings

def geocode(address:str)->tuple[float,float]:
    try:
        response=httpx.get(f"{settings.geocoder_url.rstrip('/')}/search",params={"q":address,"format":"jsonv2","limit":1,"countrycodes":"br"},headers={"User-Agent":settings.map_user_agent},timeout=15)
        response.raise_for_status(); items=response.json()
    except (httpx.HTTPError,ValueError) as error: raise HTTPException(502,"Não foi possível consultar o endereço") from error
    if not items: raise HTTPException(422,f"Endereço não localizado: {address}")
    return float(items[0]["lat"]),float(items[0]["lon"])

def calculate_route(points:list[tuple[float,float]],roundtrip:bool,optimize:bool)->dict:
    coordinates=";".join(f"{lon},{lat}" for lat,lon in points)
    if optimize:
        path=f"/trip/v1/driving/{coordinates}"; params={"source":"first","roundtrip":str(roundtrip).lower(),"destination":"any" if roundtrip else "last","overview":"full","geometries":"geojson","steps":"false"}
    else:
        path=f"/route/v1/driving/{coordinates}"; params={"overview":"full","geometries":"geojson","steps":"false"}
    try:
        response=httpx.get(f"{settings.routing_url.rstrip('/')}{path}",params=params,timeout=25); response.raise_for_status(); result=response.json()
    except (httpx.HTTPError,ValueError) as error: raise HTTPException(502,"Não foi possível calcular a rota") from error
    routes=result.get("trips") if optimize else result.get("routes")
    if not routes: raise HTTPException(422,"Não foi encontrada uma rota entre os endereços")
    order=list(range(len(points)))
    if optimize: order=[index for index,_ in sorted(enumerate(result["waypoints"]),key=lambda item:item[1]["waypoint_index"])]
    return {"route":routes[0],"order":order}

def money(value:Decimal)->Decimal: return value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
