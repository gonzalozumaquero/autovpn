import uuid
import subprocess
from pathlib import Path
from app.config import PEERS_DIR
from app.utils import ensure_dir

# ESTA RUTA DEBE APUNTAR A LA CLAVE PUBLICA DEL SERVIDOR INTERMEDIARIO
SERVER_PUBLIC_KEY = "<REEMPLAZAR_CON_CLAVE_PUBLICA_REAL>"
SERVER_ENDPOINT = "vpn.example.com:51820"  # REEMPLAZAR EN PRODUCCIÓN
VPN_ADDRESS_BASE = "10.13.13."

def generate_real_peer_config(name: str) -> tuple[str, str]:
    peer_id = str(uuid.uuid4())
    peer_dir = Path(PEERS_DIR) / name
    ensure_dir(peer_dir)

    # GENERAR CLAVE PRIVADA
    private_key = subprocess.check_output(["wg", "genkey"]).decode().strip()

    # DERIVAR CLAVE PUBLICA A PARTIR DE LA PRIVADA
    public_key = subprocess.run(
        ["wg", "pubkey"],
        input=private_key.encode(),
        capture_output=True,
        check=True
    ).stdout.decode().strip()

    # GUARDAR CLAVES EN ARCHIVOS
    (peer_dir / "privatekey").write_text(private_key)
    (peer_dir / "publickey").write_text(public_key)

    # GENERAR IP INTERNA DEL PEER (simple y temporal)
    last_octet = 10 + len(list(peer_dir.parent.iterdir()))
    vpn_ip = f"{VPN_ADDRESS_BASE}{last_octet}"

    # CREAR ARCHIVO .CONF REAL
    config = f"""
[Interface]
PrivateKey = {private_key}
Address = {vpn_ip}/32
DNS = 1.1.1.1

[Peer]
PublicKey = {SERVER_PUBLIC_KEY}
Endpoint = {SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""

    (peer_dir / f"{name}.conf").write_text(config.strip())
    return peer_id, config.strip()

def get_peer_config(name: str) -> str:
    # CARGO EL ARCHIVO .CONF SI EXISTE
    conf_path = Path(PEERS_DIR) / name / f"{name}.conf"
    if not conf_path.exists():
        raise FileNotFoundError(f"Peer config for '{name}' not found")
    return conf_path.read_text()
