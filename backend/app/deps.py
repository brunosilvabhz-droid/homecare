from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, Role, Subscription, Organization
from app.core.subscriptions import subscription_access
bearer=HTTPBearer()
def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer), db:Session=Depends(get_db)):
    user_id=decode_token(credentials.credentials)
    user=db.get(User,user_id) if user_id else None
    if not user or not user.is_active: raise HTTPException(401,"Sessão inválida")
    return user
def account_professional(user:User=Depends(current_user)):
    if user.role not in (Role.PROFESSIONAL,Role.COMPANY_ADMIN,Role.COORDINATOR,Role.ADMIN): raise HTTPException(403,"Acesso restrito")
    return user
def professional(user:User=Depends(account_professional),db:Session=Depends(get_db)):
    if user.role==Role.ADMIN: return user
    item=db.query(Subscription).filter(Subscription.organization_id==user.organization_id).first()
    if subscription_access(item)["blocked"]: raise HTTPException(402,{"code":"subscription_blocked","message":"Seu plano expirou. Contrate um plano para reativar o acesso."})
    return user
def admin(user:User=Depends(current_user)):
    if user.role != Role.ADMIN: raise HTTPException(403,"Acesso administrativo restrito")
    return user
def company_manager(user:User=Depends(current_user),db:Session=Depends(get_db)):
    organization=db.get(Organization,user.organization_id)
    if not organization or organization.account_type!="company" or user.role not in (Role.COMPANY_ADMIN,Role.ADMIN): raise HTTPException(403,"Acesso restrito ao administrador da empresa")
    return user
def company_operator(user:User=Depends(current_user),db:Session=Depends(get_db)):
    organization=db.get(Organization,user.organization_id)
    if not organization or organization.account_type!="company" or user.role not in (Role.COMPANY_ADMIN,Role.COORDINATOR,Role.ADMIN): raise HTTPException(403,"Acesso restrito à coordenação da empresa")
    return user
def financial_manager(user:User=Depends(account_professional),db:Session=Depends(get_db)):
    organization=db.get(Organization,user.organization_id)
    if organization and organization.account_type=="company" and user.role not in (Role.COMPANY_ADMIN,Role.ADMIN): raise HTTPException(403,"Financeiro disponível somente para o administrador da empresa")
    return user
def finance_manager(user:User=Depends(professional),db:Session=Depends(get_db)):
    organization=db.get(Organization,user.organization_id)
    if organization and organization.account_type=="company" and user.role not in (Role.COMPANY_ADMIN,Role.ADMIN): raise HTTPException(403,"Financeiro disponível somente para o administrador da empresa")
    return user
