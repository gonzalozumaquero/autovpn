import os
from pathlib import Path

# Carpeta donde se guardan los archivos de peers
PEERS_DIR = os.getenv("PEERS_DIR", str(Path(__file__).resolve().parent.parent / "peers"))

# SE AÑDIRÁN EN UNA FASE MAS AVANZADA DE LA IMPLEMENTACION
