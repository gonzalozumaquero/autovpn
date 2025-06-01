from fastapi import APIRouter, HTTPException
from app.models.peer import PeerCreateRequest, PeerConfigResponse
from app.services.wg_manager import generate_real_peer_config, get_peer_config
from app.utils import is_valid_peer_name

router = APIRouter()

@router.post("/", response_model=PeerConfigResponse)
def create_peer(request: PeerCreateRequest):
    # VALIDAR QUE EL NOMBRE DEL PEER SEA SEGURO Y COMPATIBLE CON EL SISTEMA DE ARCHIVOS
    if not is_valid_peer_name(request.name):
        raise HTTPException(status_code=400, detail="Nombre de peer no válido")

    # LLAMAR A LA FUNCION QUE GENERA UN .CONF FICTICIO Y LO GUARDA EN DISCO
    # ESTO DEBERÁ CAMBIARSE MÁS ADELANTE PARA USAR CLAVES REALES CON wg genkey
    peer_id, config = generate_fake_peer_config(request.name)

    # DEVUELVE EL ID DEL PEER Y SU CONFIGURACION .CONF COMO TEXTO PLANO
    return PeerConfigResponse(peer_id=peer_id, config=config)

@router.get("/{name}/config", response_model=PeerConfigResponse)
def get_peer_configuration(name: str):
    # VALIDAR NOMBRE ANTES DE CARGAR EL ARCHIVO
    if not is_valid_peer_name(name):
        raise HTTPException(status_code=400, detail="Nombre de peer no válido")

    try:
        # CARGO EL CONTENIDO DEL ARCHIVO .CONF GENERADO ANTERIORMENTE
        config = get_peer_config(name)
        return PeerConfigResponse(peer_id=name, config=config)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Archivo de configuración no encontrado para {name}")

