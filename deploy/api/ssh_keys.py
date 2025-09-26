import os
import subprocess
from pathlib import Path

STATE_DIR = Path("/app/state")
PRIVATE_KEY = STATE_DIR / "autovpn_id_rsa"
PUBLIC_KEY = STATE_DIR / "autovpn_id_rsa.pub"

def ensure_ssh_key():
    """
    Comprueba si existe un par de claves SSH en /app/state.
    Si no existe, lo genera automáticamente con ssh-keygen.
    Devuelve la ruta al fichero de clave privada.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if not PRIVATE_KEY.exists() or not PUBLIC_KEY.exists():
        cmd = [
            "ssh-keygen",
            "-t", "rsa",
            "-b", "4096",
            "-f", str(PRIVATE_KEY),
            "-N", ""  # sin passphrase
        ]
        subprocess.run(cmd, check=True)
        print(f"[AutoVPN] Generada nueva clave SSH en {PRIVATE_KEY}")

    return str(PRIVATE_KEY)
