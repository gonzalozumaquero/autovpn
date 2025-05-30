from pathlib import Path

def ensure_dir(path: Path):
    # SI NO EXISTE LA CARPETA, LA CREO
    path.mkdir(parents=True, exist_ok=True)

def is_valid_peer_name(name: str) -> bool:
    # SOLO NOMBRES ALFANUMÉRICOS Y GUIONES BAJOS
    return name.isidentifier()
