import io, qrcode, os, pyotp
from fastapi import FastAPI, Depends, HTTPException, status, Response, Body
from fastapi.responses import StreamingResponse, PlainTextResponse, JSONResponse
from sqlmodel import select
from app.db import init_db, get_session
from app.models import User, Peer
from app.auth import *
from app.deps import current_user_email
from app.wg import gen_keypair, server_public_key, add_peer, remove_peer, render_client_conf, allocate_ip
from sqlmodel import Session
from app.db import engine, Session
from fastapi import Query
from .wg import container_control, wg_show


app = FastAPI(title="AutoVPN API")

@app.on_event("startup")
def _startup():
    init_db()
    seed_admin()

@app.get("/health")
def health():
    return {"status":"ok"}

def seed_admin():
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_hash  = os.getenv("ADMIN_PASSWORD_HASH")
    if not admin_email or not admin_hash:
        return
    with Session(engine) as s:
        existing = s.exec(select(User).where(User.email == admin_email)).first()
        if existing:
            return
        u = User(email=admin_email, password_hash=admin_hash, totp_enabled=False)
        s.add(u); s.commit()

@app.get("/api/status")   # <- nota: ahora prefijo /api en todas las rutas
def api_status(email=Depends(current_user_email)):
    # Señal mínima de vida
    return {"api":"ok"}

@app.get("/api/wireguard/status")
def wireguard_status(email=Depends(current_user_email)):
    return wg_show()

@app.post("/api/wireguard/{action}")
def wireguard_action(action: str, email=Depends(current_user_email)):
    if action not in {"start","stop","restart"}:
        raise HTTPException(status_code=400, detail="invalid action")
    return container_control(action)

@app.get("/api/peers")
def list_peers(email=Depends(current_user_email), s: Session = Depends(get_session)):
    # listado simple
    q = s.exec(select(Peer)).all()
    return [{"id":p.id,"name":p.name,"ip":p.client_ip,"revoked":p.revoked_at is not None,"created_at":p.created_at} for p in q]


# --- login / totp ---
@app.post("/auth/login")
def login(email: str = Body(...), password: str = Body(...), s: Session = Depends(get_session)):
    u = s.exec(select(User).where(User.email==email)).first()
    if not u or not verify_pwd(password, u.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    if u.totp_enabled:
        temp = make_token(u.email, minutes=5, kind="mfa_tmp")
        return {"mfa_required": True, "temp_token": temp}
    # sin TOTP: login directo
    access = make_token(u.email, ACCESS_MIN, "access")
    refresh = make_token(u.email, REFRESH_DAYS*24*60, "refresh")
    resp = JSONResponse({"ok": True})
    set_auth_cookies(resp, access, refresh)
    return resp

@app.post("/auth/mfa/verify")
def mfa_verify(code: str = Body(...), temp_token: str = Body(...), s: Session = Depends(get_session)):
    try:
        payload = jwt.decode(temp_token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("kind") != "mfa_tmp":
            raise Exception("wrong kind")
        email = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    u = s.exec(select(User).where(User.email==email)).first()
    if not u or not u.totp_enabled or not u.totp_secret:
        raise HTTPException(status_code=401, detail="mfa not enabled")
    if not verify_totp(u.totp_secret, code):
        raise HTTPException(status_code=401, detail="bad mfa code")
    access = make_token(email, ACCESS_MIN, "access", extra={"mfa_time": int(time.time())})
    refresh = make_token(email, REFRESH_DAYS*24*60, "refresh")
    resp = JSONResponse({"ok": True})
    set_auth_cookies(resp, access, refresh)
    return resp

@app.post("/auth/totp/enroll")
def totp_enroll(password: str = Body(...), email=Depends(current_user_email), s: Session = Depends(get_session)):
    u = s.exec(select(User).where(User.email==email)).first()
    if not u or not verify_pwd(password, u.password_hash):
        raise HTTPException(status_code=401)
    if u.totp_enabled:
        raise HTTPException(status_code=400, detail="already enabled")
    secret = pyotp.random_base32()
    u.totp_secret = secret
    s.add(u); s.commit()
    uri = provision_uri(secret, u.email)
    # devuelvo QR png in-line
    img = qrcode.make(uri)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@app.post("/auth/totp/enable")
def totp_enable(code: str = Body(...), email=Depends(current_user_email), s: Session = Depends(get_session)):
    u = s.exec(select(User).where(User.email==email)).first()
    if not u or not u.totp_secret:
        raise HTTPException(status_code=400)
    if not verify_totp(u.totp_secret, code):
        raise HTTPException(status_code=401)
    u.totp_enabled = True
    s.add(u); s.commit()
    return {"enabled": True}

@app.post("/auth/logout")
def logout():
    resp = JSONResponse({"ok": True})
    clear_auth_cookies(resp)
    return resp

# --- peers ---
@app.post("/peers")
def create_peer(name: str = Body(...), email=Depends(current_user_email), s: Session = Depends(get_session)):
    # muy simple: siguiente IP = 10.13.13.X/32 donde X = 10 + count
    count = s.exec(select(Peer)).count() if hasattr(s, "count") else len(s.exec(select(Peer)).all())
    client_priv, client_pub = gen_keypair()
    server_pub = server_public_key()
    client_ip_cidr = allocate_ip(10 + count)
    add_peer(server_pub, client_pub, client_ip_cidr)
    peer = Peer(user_id=0, name=name, client_private=client_priv, client_public=client_pub, client_ip=client_ip_cidr)
    s.add(peer); s.commit(); s.refresh(peer)
    return {"id": peer.id, "name": name, "ip": peer.client_ip}

@app.get("/peers/{peer_id}/config")
def download_conf(peer_id: int, email=Depends(current_user_email), s: Session = Depends(get_session)):
    peer = s.get(Peer, peer_id)
    if not peer or peer.revoked_at is not None:
        raise HTTPException(status_code=404)
    server_pub = server_public_key()
    conf = render_client_conf(peer.client_private, peer.client_ip, server_pub)
    headers = {"Content-Disposition": f'attachment; filename="AutoVPN-{peer.name}.conf"'}
    return PlainTextResponse(content=conf, headers=headers)

@app.get("/peers/{peer_id}/qr")
def download_qr(peer_id: int, email=Depends(current_user_email), s: Session = Depends(get_session)):
    peer = s.get(Peer, peer_id)
    if not peer or peer.revoked_at is not None:
        raise HTTPException(status_code=404)
    server_pub = server_public_key()
    conf = render_client_conf(peer.client_private, peer.client_ip, server_pub)
    img = qrcode.make(conf)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

