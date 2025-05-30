from fastapi import APIRouter
from pydantic import BaseModel
import uuid

router = APIRouter()

# Modelo de entrada
class PeerCreateRequest(BaseModel):
    name: str

# Modelo de salida
class PeerConfigResponse(BaseModel):
    peer_id: str
    config: str

@router.post("/", response_model=PeerConfigResponse)
def create_peer(request: PeerCreateRequest):
    # Simular creación de claves y archivo .conf
    peer_id = str(uuid.uuid4())

    # Simulación de archivo de configuración
    config = f"""
[Interface]
PrivateKey = <PRIVATE_KEY_{request.name}>
Address = 10.13.13.10/32
DNS = 1.1.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = vpn.example.com:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""

    return PeerConfigResponse(peer_id=peer_id, config=config.strip())

