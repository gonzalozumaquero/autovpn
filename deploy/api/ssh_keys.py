# ssh_keys.py
import os
import subprocess
import time
from pathlib import Path
from contextlib import contextmanager

STATE_DIR = Path(os.getenv("STATE_DIR", "/app/state")).resolve()
KEY_NAME  = os.getenv("KEY_NAME", "autovpn_id")
PRIVATE_KEY = STATE_DIR / f"{KEY_NAME}"
PUBLIC_KEY  = STATE_DIR / f"{KEY_NAME}.pub"
LOCK_FILE   = STATE_DIR / f".{KEY_NAME}.lock"


@contextmanager
def _file_lock(path: Path, retries: int = 50, delay: float = 0.1):
    """
    Bloqueo simple por fichero. No es a prueba de todo, pero evita
    carreras típicas en contenedor único.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(retries):
        try:
            # os.O_EXCL falla si ya existe
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            try:
                yield
            finally:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
            return
        except FileExistsError:
            time.sleep(delay)
    # si no conseguimos el lock, seguimos igualmente (mejor no bloquear indef)
    yield


def _chmod_safe():
    try:
        STATE_DIR.chmod(0o700)
    except Exception:
        pass
    if PRIVATE_KEY.exists():
        try:
            PRIVATE_KEY.chmod(0o600)
        except Exception:
            pass
    if PUBLIC_KEY.exists():
        try:
            PUBLIC_KEY.chmod(0o644)
        except Exception:
            pass


def _have_fips_mode() -> bool:
    # heurística simple: si existe /proc/sys/crypto/fips_enabled y vale 1
    try:
        p = Path("/proc/sys/crypto/fips_enabled")
        return p.exists() and p.read_text().strip() == "1"
    except Exception:
        return False


def _generate_keypair():
    """
    Genera un par de claves si no existen. Prefiere ED25519; si el
    sistema está en FIPS, cae a RSA-4096.
    """
    alg_args = ["-t", "ed25519", "-a", "100"]  # -a: rounds KDF
    if _have_fips_mode():
        alg_args = ["-t", "rsa", "-b", "4096"]

    cmd = [
        "ssh-keygen",
        *alg_args,
        "-f", str(PRIVATE_KEY),
        "-N", "",                # sin passphrase (automatización)
        "-C", "autovpn-installer",
    ]
    subprocess.run(cmd, check=True)


def _ensure_pub_from_priv():
    """
    Si existe la privada pero falta la pública, derivarla.
    """
    if PRIVATE_KEY.exists() and not PUBLIC_KEY.exists():
        pub = subprocess.check_output(["ssh-keygen", "-y", "-f", str(PRIVATE_KEY)], text=True)
        PUBLIC_KEY.write_text(pub if pub.endswith("\n") else pub + "\n", encoding="utf-8")


def ensure_ssh_key() -> str:
    """
    Garantiza que exista un par de claves en STATE_DIR. Devuelve la ruta de la privada.
    """
    with _file_lock(LOCK_FILE):
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        if not PRIVATE_KEY.exists() or not PUBLIC_KEY.exists():
            _generate_keypair()
            print(f"[AutoVPN] Generada nueva clave SSH en {PRIVATE_KEY}")

        # Por si falta la .pub (p.ej. volumen viejo con solo .key)
        _ensure_pub_from_priv()

        # Asegurar permisos
        _chmod_safe()

    return str(PRIVATE_KEY)


def get_key_paths() -> tuple[str, str]:
    """
    Devuelve (ruta_privada, ruta_publica). No genera nada.
    """
    return str(PRIVATE_KEY), str(PUBLIC_KEY)

