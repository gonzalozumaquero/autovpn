from fastapi import Cookie, HTTPException, status
import jwt, os

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")

def current_user_email(access: str | None = Cookie(default=None)):
    if not access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        payload = jwt.decode(access, JWT_SECRET, algorithms=["HS256"])
        if payload.get("kind") != "access":
            raise Exception("wrong kind")
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

