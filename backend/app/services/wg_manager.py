import uuid
from pathlib import Path
from app.config import PEERS_DIR

def generate_fake_peer_config(name: str) -> str:
    # Ruta de guardado del archivo simulado (más adelante se usará para escritura real)
    peer_id = str(uuid.uuid4())
    peer_dir = Path(PEERS_DIR) / name
    peer_dir.mkdir(parents=True, exist_ok=True)

    config = f"""
[Interface]
PrivateKey = <PRIVATE_KEY_{name}>
Address = 10.13.13.10/32
DNS = 1.1.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = vpn.example.com:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""

    # Escribir archivo simulado
    with open(peer_dir / f"{name}.conf", "w") as f:
        f.write(config.strip())

    return peer_id, config.strip()


def get_peer_config(name: str) -> str:
    # CARGO EL ARCHIVO .CONF SI EXISTE
    conf_path = Path(PEERS_DIR) / name / f"{name}.conf"
    if not conf_path.exists():
        raise FileNotFoundError(f"Peer config for '{name}' not found")
    return conf_path.read_text()
