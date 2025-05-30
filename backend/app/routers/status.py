from fastapi import APIRouter
from pathlib import Path
from app.config import PEERS_DIR

router = APIRouter()

@router.get("/", tags=["Status"])
def server_status():
    # DEVOLVER CUÁNTOS PEERS EXISTEN ACTUALMENTE
    peers_path = Path(PEERS_DIR)
    count = len([d for d in peers_path.iterdir() if d.is_dir()]) if peers_path.exists() else 0
    return {
        "status": "ok",
        "peer_count": count
    }
