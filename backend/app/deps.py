from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, Role
bearer=HTTPBearer()
def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer), db:Session=Depends(get_db)):
    user_id=decode_token(credentials.credentials)
    user=db.get(User,user_id) if user_id else None
    if not user or not user.is_active: raise HTTPException(401,"Sessão inválida")
    return user
def professional(user:User=Depends(current_user)):
    if user.role not in (Role.PROFESSIONAL,Role.ADMIN): raise HTTPException(403,"Acesso restrito")
    return user
def admin(user:User=Depends(current_user)):
    if user.role != Role.ADMIN: raise HTTPException(403,"Acesso administrativo restrito")
    return user
