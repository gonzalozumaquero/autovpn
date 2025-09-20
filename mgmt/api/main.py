from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import io, qrcode
from schemas import WGParamsReq , WGParamsResp

SERVER_PUBLIC_KEY = "PUBKEY_DEL_SERVIDOR"  # cámbiar por el real
LISTEN_PORT = 51820

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en prod limita a tu dominio
    allow_methods=["*"],
    allow_headers=["*"],
)

class WGRequest(BaseModel):
    server_ip: str
    ssh_user: str
    client_name: str = "mi-dispositivo"

@app.post("/wg/server_params", response_model=WGParamsResp)
def wg_server_params(req: WGParamsReq):
    client_address = "10.13.13.2/32"  # TODO: gestión dinámica de pool

    # Llamada a Ansible para añadir peer
    cmd = [
        "ansible-playbook", "deploy/ansible/add_peer.yml",
        "-e", f"peer_name={req.peer_name}",
        "-e", f"peer_pubkey={req.peer_public_key}",
        "-e", f"client_address={client_address}"
    ]
    # subprocess.run(cmd, check=True)
    endpoint_ip = req.server_hint or "MI_IP_PUBLICA"
    endpoint = f"{endpoint_ip}:{LISTEN_PORT}"

    return WGParamsResp(
        endpoint=endpoint,
        server_public_key=SERVER_PUBLIC_KEY,
        dns="10.13.13.1",
        allowed_ips="0.0.0.0/0, ::/0",
        client_address=client_address
        )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/wg/config")
def wg_config(req: WGRequest):
    # En el MVP la clave privada del cliente la genera el cliente.
    # Aquí solo devolvemos una plantilla de ejemplo (mock).
    conf = f"""[Interface]
PrivateKey = REEMPLAZA_EN_CLIENTE
Address = 10.13.13.2/32
DNS = 10.13.13.1

[Peer]
PublicKey = XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PresharedKey = YYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
Endpoint = {req.server_ip}:51820
AllowedIPs = 0.0.0.0/0, ::/0
"""

    # Genera QR (útil para móviles)
    img = qrcode.make(conf)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Empaquetar en multipart no es estrictamente necesario para el MVP.
    # Devolvemos solo el .conf; el QR lo puedes pedir en otro endpoint si prefieres.
    return Response(content=conf, media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{req.client_name}.conf"'}
    )

@app.post("/wg/qrcode")
def wg_qrcode(req: WGRequest):
    # Mismo conf que arriba (mock), sólo para QR demo
    conf = f"[Interface]\nPrivateKey = REEMPLAZA_EN_CLIENTE\nAddress = 10.13.13.2/32\n\n[Peer]\nEndpoint = {req.server_ip}:51820\nAllowedIPs = 0.0.0.0/0\n"
    img = qrcode.make(conf)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

