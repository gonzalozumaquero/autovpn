# deploy/api/bootstrap.py
from fastapi import APIRouter, HTTPException, Response, Request, Query
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
    xf_proto = req.headers.get("x-forwarded-proto")
    xf_host  = req.headers.get("x-forwarded-host")
    xf_port  = req.headers.get("x-forwarded-port")
    if xf_proto and xf_host:
        host = xf_host
        # Añade puerto no estándar si viene informado
        if xf_port and ((xf_proto == "http" and xf_port not in ("80",)) or
                        (xf_proto == "https" and xf_port not in ("443",))):
            host = f"{host}:{xf_port}"
        return f"{xf_proto}://{host}"
    return str(req.base_url).rstrip("/")

def _render_script(base_url: str, user: str, allow_nopasswd: bool) -> str:
    """
    Renderiza un script bash idempotente para:
      - Crear usuario de servicio si no existe
      - Autorizar clave pública del installer en su authorized_keys (sin duplicados)
      - (Opcional) Conceder sudo NOPASSWD validado con visudo
      - Instalar python3 (para Ansible) si falta
      - Dejar marca de estado en /var/lib/autovpn/bootstrap.json
    """
    base_url = base_url.rstrip("/")
    pubkey_url = urllib.parse.urljoin(base_url + "/", "bootstrap/pubkey")
    sudo_clause = f"""
# 3) (Opcional) sudo sin password para automatizar Ansible
if [ "{'1' if allow_nopasswd else '0'}" = "1" ]; then
  echo "{user} ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/90-autovpn >/dev/null
  sudo chmod 440 /etc/sudoers.d/90-autovpn
  # Validar antes de continuar
  if ! sudo visudo -cf /etc/sudoers.d/90-autovpn >/dev/null; then
    echo "ERROR: entrada de sudoers inválida" >&2
    sudo rm -f /etc/sudoers.d/90-autovpn
    exit 1
  fi
fi
""".strip()

    script = f"""#!/usr/bin/env bash
set -euo pipefail

USER="{user}"

# 0) Requisitos previos
if ! command -v curl >/dev/null 2>&1; then
  echo "Instala 'curl' y vuelve a ejecutar." >&2
  exit 1
fi

# 1) Crear usuario de servicio si no existe
if ! id "$USER" >/dev/null 2>&1; then
  # shell por defecto bash, home en /home/$USER
  sudo useradd -m -s /bin/bash "$USER"
fi

home="$(getent passwd "$USER" | cut -d: -f6)"
sudo mkdir -p "$home/.ssh"
sudo chmod 700 "$home/.ssh"
sudo chown -R "$USER:$USER" "$home/.ssh"

# 2) Autorizar la clave pública del installer (sin duplicados)
tmp_pub="$(mktemp)"
curl -fsSL {pubkey_url} -o "$tmp_pub"
if [ ! -s "$tmp_pub" ]; then
  echo "No se pudo descargar pubkey desde {pubkey_url}" >&2
  exit 1
fi
# Añadir solo si no existe
sudo touch "$home/.ssh/authorized_keys"
sudo chmod 600 "$home/.ssh/authorized_keys"
if ! sudo grep -F -q "$(cat "$tmp_pub")" "$home/.ssh/authorized_keys"; then
  sudo bash -c "cat '$tmp_pub' >> '$home/.ssh/authorized_keys'"
fi
sudo chown "$USER:$USER" "$home/.ssh/authorized_keys"
rm -f "$tmp_pub"

{sudo_clause}

# 4) Asegurar python3 para Ansible
if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3
  else
    echo "Gestor de paquetes no reconocido. Instala python3 manualmente." >&2
    exit 1
  fi
fi

# 5) Marca de estado
sudo mkdir -p /var/lib/autovpn
echo '{{"done":true,"user":"{user}","ts":"'$(
  date -u +"%Y-%m-%dT%H:%M:%SZ"
)'"}}' | sudo tee /var/lib/autovpn/bootstrap.json >/dev/null
sudo chmod 644 /var/lib/autovpn/bootstrap.json

echo "Bootstrap completado para usuario '{user}'."
"""
    return script

@router.get("/pubkey", response_class=Response)
def pubkey():
    """
    Devuelve la clave pública del installer (para meterla en authorized_keys).
    """
    if not PUBKEY_PATH.exists():
        raise HTTPException(status_code=500, detail="Public key not found")
    return Response(content=PUBKEY_PATH.read_text(), media_type="text/plain")

@router.get("/script", response_class=Response)
def script(
    req: Request,
    user: str = Query("autovpn", description="Usuario de servicio a crear/usar"),
    nopasswd: int = Query(1, ge=0, le=1, description="1 => sudo NOPASSWD, 0 => no tocar sudoers"),
):
    """
    Entrega un script bash parametrizable:
      - ?user=autovpn (por defecto)
      - ?nopasswd=1   (por defecto; usa 0 para evitar sudoers)
    Uso recomendado:
      curl -fsSL https://<installer-host>/bootstrap/script | bash
    """
    base_url = _choose_base_url(req)
    content = _render_script(base_url, user=user, allow_nopasswd=bool(nopasswd))
    return Response(
        content=content,
        media_type="text/x-shellscript",
        headers={"Content-Disposition": 'attachment; filename="bootstrap.sh"'},
    )

