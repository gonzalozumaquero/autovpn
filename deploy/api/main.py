# backend/app/main.py
import os
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

# ====== MODO de ejecución ======
APP_MODE = os.getenv("APP_MODE", "server").lower()  # "installer" | "server"

# ====== App base ======
app = FastAPI(
    title="AutoVPN Backend",
    description="API para instalación asistida (installer) y gestión de AutoVPN (server).",
    version="0.2.0",
)

# ====== CORS ======
# En desarrollo: frontend local vite en :3000
FRONTEND_ORIGINS = [
    os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
    "http://127.0.0.1:3000",
]
# Si necesitas abrir más orígenes, agrega aquí o usa "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== Salud ======
@app.get("/health")
def health():
    return {"status": "ok", "mode": APP_MODE}

# ====== Rutas según MODO ======
if APP_MODE == "installer":
    # --- Backend LOCAL para instalación asistida (FASE 1) ---
    # Endpoints esperados por tu nuevo frontend:
    #  POST /install/check-ssh
    #  POST /install/config
    #  POST /install/run
    #  GET  /install/logs/{run_id}    (SSE)
    try:
        # Coloca este módulo en backend/app/routers/install.py (según lo que ya te pasé)
        from routers import install
        app.include_router(install.router, prefix="", tags=["Install"])
    except Exception as e:
        raise RuntimeError(
            f"No se pudo cargar el router de instalación asistida: {e}"
        )

else:
    # --- Backend del SERVIDOR (FASE 2) ---
    # Mantiene tus módulos existentes: peers/status/bootstrap/orchestrator/ssh_keys
    import io, qrcode
    from pydantic import BaseModel
    from schemas import WGParamsReq, WGParamsResp
    from pool import get_client_ip
    from orchestrator import add_wg_peer
    from ssh_keys import ensure_ssh_key
    from bootstrap import router as bootstrap_router

    # Garantiza clave pública/privada que expone /bootstrap/pubkey (si tu bootstrap lo usa)
    ensure_ssh_key()

    # Subrouter de bootstrap
    app.include_router(bootstrap_router, prefix="/bootstrap", tags=["Bootstrap"])

    WG_PORT = int(os.getenv("WG_PORT", "51820"))

    class WGRequest(BaseModel):
        server_ip: str
        ssh_user: str
        client_name: str = "mi-dispositivo"

    @app.post("/wg/server_params", response_model=WGParamsResp, tags=["WireGuard"])
    def wg_server_params(req: WGParamsReq):
        """
        Devuelve parámetros del servidor WG + da de alta el peer (vía orchestrator).
        Este endpoint está pensado para usarse desde el frontend del SERVIDOR (FASE 2).
        """
        try:
            client_address = get_client_ip(req.peer_name)
            ssh_user = req.ssh_user or "ubuntu"

            # Alta real del peer en el servidor destino (puede usar Ansible/script)
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
            client_address=client_address,
        )

    @app.post("/wg/qrcode", tags=["WireGuard"])
    def wg_qrcode(req: WGRequest):
        """
        Genera un QR PNG con una configuración de ejemplo.
        Para producción, genera el .conf real antes y renderiza ese contenido.
        """
        conf = (
            f"[Interface]\n"
            f"PrivateKey = REEMPLAZA_EN_CLIENTE\n"
            f"Address = 10.13.13.2/32\n\n"
            f"[Peer]\n"
            f"Endpoint = {req.server_ip}:{WG_PORT}\n"
            f"AllowedIPs = 0.0.0.0/0\n"
        )
        img = qrcode.make(conf)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")

    # Si tenías más routers (peers, status), los puedes mantener:
    try:
        from routers import peers, status
        app.include_router(peers.router, prefix="/peers", tags=["Peers"])
        app.include_router(status.router, prefix="/status", tags=["Status"])
    except Exception:
        # Son opcionales; ignora si aún no los tienes listos.
        pass
