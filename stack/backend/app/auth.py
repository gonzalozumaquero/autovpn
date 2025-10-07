import os, time
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from passlib.hash import bcrypt
import pyotp
from fastapi import HTTPException, Response

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
ACCESS_MIN = int(os.getenv("JWT_ACCESS_TTL_MIN", "15"))
REFRESH_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "7"))
TOTP_ISSUER = os.getenv("TOTP_ISSUER", "AutoVPN")

def hash_pwd(p: str) -> str:
    return bcrypt.hash(p)

def verify_pwd(p: str, h: str) -> bool:
    return bcrypt.verify(p, h)

def make_token(sub: str, minutes: int, kind: str, extra: Optional[dict]=None):
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=minutes)).timestamp()), "kind": kind}
    if extra: payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def set_auth_cookies(resp: Response, access: str, refresh: str):
    # Cookies seguras
    resp.set_cookie("access", access, httponly=True, secure=True, samesite="lax", max_age=ACCESS_MIN*60)
    resp.set_cookie("refresh", refresh, httponly=True, secure=True, samesite="lax", max_age=REFRESH_DAYS*24*3600)

def clear_auth_cookies(resp: Response):
    resp.delete_cookie("access")
    resp.delete_cookie("refresh")

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # ±30s

def provision_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)

