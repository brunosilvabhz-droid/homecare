from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from pwdlib import PasswordHash
from app.core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"
def hash_password(value: str) -> str: return password_hash.hash(value)
def verify_password(value: str, hashed: str) -> bool: return password_hash.verify(value, hashed)
def create_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.jwt_secret, algorithm=ALGORITHM)
def create_email_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.email_verification_expire_hours)
    return jwt.encode({"sub": user_id, "purpose": "verify_email", "exp": exp}, settings.jwt_secret, algorithm=ALGORITHM)
def decode_email_token(token: str) -> str | None:
    try:
        payload=jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload.get("sub") if payload.get("purpose")=="verify_email" else None
    except JWTError: return None
def create_password_reset_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode({"sub": user_id, "purpose": "password_reset", "exp": exp}, settings.jwt_secret, algorithm=ALGORITHM)
def decode_password_reset_token(token: str) -> str | None:
    try:
        payload=jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload.get("sub") if payload.get("purpose")=="password_reset" else None
    except JWTError: return None
def decode_token(token: str) -> str | None:
    try: return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM]).get("sub")
    except JWTError: return None
