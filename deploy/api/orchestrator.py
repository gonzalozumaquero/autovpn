# orchestrator.py
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from ssh_keys import ensure_ssh_key  # garantiza la clave del controlador

SSH_KEY_PATH = ensure_ssh_key()
WG_PORT = int(os.getenv("WG_PORT", "51820"))
WG_MODE = os.getenv("WG_MODE", "container").lower()  # "container" | "host"
WG_CONTAINER = os.getenv("WG_CONTAINER_NAME", "wireguard")


# ---------------------------
# Utilidades Ansible (ad-hoc)
# ---------------------------

def _write_temp_inventory_ini(server_ip: str, ssh_user: str, extra: Optional[dict] = None) -> str:
    """
    Genera un inventario INI temporal para un único host [target]
    """
    lines = [
        "[target]",
        f"srv ansible_host={server_ip} "
        f"ansible_user={ssh_user} "
        f"ansible_ssh_private_key_file={SSH_KEY_PATH} "
        f"ansible_python_interpreter=/usr/bin/python3 "
        'ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"',
        "",
        "[target:vars]",
        "ansible_become=true",
    ]
    if extra:
        for k, v in extra.items():
            lines.append(f"{k}={v}")
    fd, path = tempfile.mkstemp(suffix=".ini", prefix="inv_")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return path


def _ansible_shell(inv_path: str, cmdline: str, become: bool = True) -> subprocess.CompletedProcess:
    """
    Ejecuta un comando remoto (módulo shell). Devuelve CompletedProcess (capturando stdout).
    """
    cmd = [
        "ansible", "-i", inv_path, "srv",
        "-m", "shell",
        "-a", cmdline,
    ]
    if become:
        cmd.insert(3, "-b")
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def _ansible_stdout(inv_path: str, cmdline: str, become: bool = True) -> str:
    res = _ansible_shell(inv_path, cmdline, become=become)
    # Filtra la salida de Ansible y devuelve la última línea no vacía
    lines = [l.strip() for l in (res.stdout or "").splitlines() if l.strip()]
    return lines[-1] if lines else ""


# ---------------------------
# Bootstrap por password (opcional)
# ---------------------------

def _bootstrap_install_key_with_password(server_ip: str, ssh_user: str, ssh_password: str):
    """
    Conexión por password (paramiko) para instalar la clave pública del controlador
    en authorized_keys del usuario remoto. Requiere que el host permita password temporalmente.
    """
    extra = {
        "ansible_connection": "paramiko",
        "ansible_password": ssh_password,
    }
    inv = _write_temp_inventory_ini(server_ip, ssh_user, extra=extra)
    pub_path = f"{SSH_KEY_PATH}.pub"
    if not Path(pub_path).exists():
        raise RuntimeError("Clave pública no encontrada para bootstrap (expected <key>.pub)")

    # Crea .ssh si no existe y añade la pubkey si no está presente
    script = rf"""
set -e
mkdir -p ~/.ssh
chmod 700 ~/.ssh
grep -q -F "$(cat {pub_path})" ~/.ssh/authorized_keys 2>/dev/null || \
  (echo "$(cat {pub_path})" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys)
echo BOOTSTRAP_OK
"""
    out = _ansible_stdout(inv, script, become=False)  # authorized_keys pertenece al usuario, no usar become
    if "BOOTSTRAP_OK" not in out:
        raise RuntimeError("No se pudo instalar la clave pública en authorized_keys")


# ---------------------------
# Alta de peer en WG (host o contenedor)
# ---------------------------

def _cmd_wg_add_peer(peer_pubkey: str, client_address: str) -> str:
    """
    Devuelve el comando shell para añadir un peer según WG_MODE.
    - host:       wg set wg0 peer <pub> allowed-ips <addr>/32
    - container:  docker exec <name> wg set wg0 peer <pub> allowed-ips <addr>/32
    """
    base = f"wg set wg0 peer {peer_pubkey} allowed-ips {client_address}"
    if WG_MODE == "host":
        return base
    # por defecto contenedor
    return f"docker exec {WG_CONTAINER} {base}"


def _cmd_wg_pubkey() -> str:
    """
    Devuelve el comando para obtener la public key del servidor wg0.
    """
    base = "wg show wg0 public-key"
    if WG_MODE == "host":
        return base
    return f"docker exec {WG_CONTAINER} {base}"


def _cmd_wg_pubkey_fallback() -> str:
    """
    Fallback para obtener la clave pública desde fichero, si la mantienes en host.
    Ajusta la ruta si tu rol las guarda en otro sitio (contenedor/volumen).
    """
    if WG_MODE == "host":
        # ejemplo típico si guardas server.key y server.pub en /etc/wireguard
        return "cat /etc/wireguard/server.pub || (wg pubkey < /etc/wireguard/server.key)"
    # En contenedor: intenta leer desde volumen montado (ajusta si usas otra ruta/imagen)
    return f"docker exec {WG_CONTAINER} sh -lc \"cat /config/server.pub || (wg show wg0 public-key)\""


# ---------------------------
# API principal
# ---------------------------

def add_wg_peer(server_ip: str, ssh_user: str, peer_pubkey: str, client_address: str,
                ssh_password: Optional[str] = None) -> str:
    """
    Alta de peer WireGuard en el servidor destino:
      1) Intenta por clave (inventario temporal con tu SSH_KEY_PATH).
      2) Si falla por permisos y se aporta ssh_password:
           - hace bootstrap (paramiko) para meter la clave pública
           - reintenta por clave
      3) Devuelve server_public_key (wg0).

    Requisitos en el servidor:
      - WG nativo (wg-quick@wg0) o contenedor accesible por 'docker exec <WG_CONTAINER>'.
      - Usuario con sudo (become) para ejecutar wg/iptables si es nativo.
    """
    # Inventario por clave
    inv_key = _write_temp_inventory_ini(
        server_ip, ssh_user,
        extra={
            # nada extra; usamos private key y become
        },
    )

    # 1) Alta del peer
    try:
        cmd_add = _cmd_wg_add_peer(peer_pubkey, client_address)
        _ansible_shell(inv_key, cmd_add, become=True)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").lower()
        needs_bootstrap = ssh_password and ("permission denied" in err or "unreachable" in err)
        if not needs_bootstrap:
            raise

        # 2) Bootstrap por password y reintento por clave
        _bootstrap_install_key_with_password(server_ip, ssh_user, ssh_password)
        _ansible_shell(inv_key, cmd_add, become=True)

    # 3) Clave pública del servidor
    try:
        server_pub = _ansible_stdout(inv_key, _cmd_wg_pubkey(), become=True)
        if not server_pub or server_pub.lower().startswith("wg:"):
            raise RuntimeError("wg show fallback")
    except Exception:
        server_pub = _ansible_stdout(inv_key, _cmd_wg_pubkey_fallback(), become=True)

    if not server_pub:
        raise RuntimeError("No se pudo obtener la clave pública de wg0")

    return server_pub

