from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import io, qrcode
from schemas import WGParamsReq , WGParamsResp
from pool import get_client_ip
from orchestrator import add_wg_peer
from ssh_keys import ensure_ssh_key
from bootstrap import router as bootstrap_router
import os

SERVER_PUBLIC_KEY = "PUBKEY_DEL_SERVIDOR"  # cámbiar por el real
LISTEN_PORT = 51820

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod usar mi dominio
    allow_methods=["*"],
    allow_headers=["*"],
)

# Garantiza que exista la clave del backend (para publicar /bootstrap/pubkey)
ensure_ssh_key()

# Monta el subrouter /bootstrap
app.include_router(bootstrap_router)

WG_PORT = int(os.getenv("WG_PORT", "51820"))


class WGRequest(BaseModel):
    server_ip: str
    ssh_user: str
    client_name: str = "mi-dispositivo"

@app.post("/wg/server_params", response_model=WGParamsResp)
def wg_server_params(req: WGParamsReq):
    try:
        client_address = get_client_ip(req.peer_name)
        ssh_user = req.ssh_user or "autovpn" 
        # Alta real del peer en el servidor destino (vía Ansible)
        server_public_key = add_wg_peer(
            server_ip=req.server_hint,
            ssh_user=ssh_user,
            peer_pubkey=req.peer_public_key,
            client_address=client_address,
            ssh_password=req.ssh_password, 
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Provisioning error: {str(e)}")

    endpoint = f"{req.server_hint}:{WG_PORT}"
    return WGParamsResp(
        endpoint=endpoint,
        server_public_key=server_public_key,
        dns="10.13.13.1",
        allowed_ips="0.0.0.0/0, ::/0",
        client_address=client_address
    )

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/wg/qrcode")
def wg_qrcode(req: WGRequest):
    # Mismo conf que arriba (mock), sólo para QR demo
    conf = f"[Interface]\nPrivateKey = REEMPLAZA_EN_CLIENTE\nAddress = 10.13.13.2/32\n\n[Peer]\nEndpoint = {req.server_ip}:51820\nAllowedIPs = 0.0.0.0/0\n"
    img = qrcode.make(conf)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

