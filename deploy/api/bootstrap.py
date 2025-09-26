# mgmt/api/bootstrap.py
from fastapi import APIRouter, HTTPException, Response, Request
from pathlib import Path
import urllib.parse

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])

STATE_DIR = Path("/app/state")
PUBKEY_PATH = STATE_DIR / "autovpn_id_rsa.pub"

def _choose_base_url(req: Request) -> str:
    """
    Devuelve el base URL correcto, respetando reverse proxies.
    Prioriza X-Forwarded-Proto/Host/Port; si no, usa request.base_url.
    """
    # 1) Intentar con X-Forwarded-*
    xf_proto = req.headers.get("x-forwarded-proto")
    xf_host  = req.headers.get("x-forwarded-host")
    xf_port  = req.headers.get("x-forwarded-port")
    if xf_proto and xf_host:
        host = xf_host
        # Si viene sin puerto pero X-Forwarded-Port existe y no es estándar, añádelo
        if xf_port and ( (xf_proto == "http" and xf_port not in ("80",)) or
                         (xf_proto == "https" and xf_port not in ("443",)) ):
            host = f"{host}:{xf_port}"
        return f"{xf_proto}://{host}"

    # 2) Fallback: request.base_url (incluye proto/host/port)
    #    e.g. http://127.0.0.1:8000/
    base = str(req.base_url).rstrip("/")
    return base

def _render_script(base_url: str) -> str:
    # Sanear (por si viene con / final)
    base_url = base_url.rstrip("/")
    pubkey_url = urllib.parse.urljoin(base_url + "/", "bootstrap/pubkey")
    script = f"""#!/usr/bin/env bash
set -euo pipefail

USER="autovpn"

# 1) Crear usuario de servicio si no existe
if ! id "$USER" >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash "$USER"
fi

home="$(getent passwd "$USER" | cut -d: -f6)"
sudo mkdir -p "$home/.ssh"
sudo chmod 700 "$home/.ssh"
sudo chown -R "$USER:$USER" "$home/.ssh"

# 2) Autorizar la clave pública de AutoVPN desde el mismo origen
curl -fsSL {base_url.rstrip("/")}/bootstrap/pubkey | sudo tee -a "$home/.ssh/authorized_keys" >/dev/null
sudo chmod 600 "$home/.ssh/authorized_keys"
sudo chown "$USER:$USER" "$home/.ssh/authorized_keys"

# 3) (Opcional) sudo sin password para automatizar Ansible
if [ -n "${{ALLOW_NOPASSWD:-1}}" ]; then
  echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/90-autovpn >/dev/null
  sudo chmod 440 /etc/sudoers.d/90-autovpn
fi

# 4) Asegurar python3 para Ansible
if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3
  fi
fi

# 5) Marca de estado
sudo mkdir -p /var/lib/autovpn
echo '{{"done":true,"user":"autovpn"}}' | sudo tee /var/lib/autovpn/bootstrap.json >/dev/null
sudo chmod 644 /var/lib/autovpn/bootstrap.json

echo "Bootstrap completado para usuario 'autovpn'."
"""
    return script

@router.get("/pubkey", response_class=Response)
def pubkey():
    if not PUBKEY_PATH.exists():
        raise HTTPException(status_code=500, detail="Public key not found")
    return Response(content=PUBKEY_PATH.read_text(), media_type="text/plain")

@router.get("/script", response_class=Response)
def script(req: Request):
    base_url = _choose_base_url(req)
    return Response(
        content=_render_script(base_url),
        media_type="text/x-shellscript",
        headers={"Content-Disposition": 'attachment; filename="bootstrap.sh"'},
    )

