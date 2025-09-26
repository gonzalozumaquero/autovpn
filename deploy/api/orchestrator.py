import os
import subprocess
import tempfile
import json
from ssh_keys import ensure_ssh_key  # from .ssh_keys import ensure_ssh_key

SSH_KEY_PATH = ensure_ssh_key()
WG_PORT = int(os.getenv("WG_PORT", "51820"))

def _write_temp_inventory(server_ip: str, ssh_user: str, extra: dict | None = None) -> str:
    inv_host = {
        "ansible_host": server_ip,
        "ansible_user": ssh_user,
        "ansible_ssh_private_key_file": SSH_KEY_PATH,
        "ansible_python_interpreter": "/usr/bin/python3",
        # Seguridad relajada para lab; en prod gestiona known_hosts
        "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
    }
    if extra:
        inv_host.update(extra)
    inv = {"all": {"hosts": {"target": inv_host}}}
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yml")
    tmp.write(json.dumps(inv))
    tmp.close()
    return tmp.name

def _run_playbook(inv_path: str, playbook_rel_path: str, extravars: dict | None = None):
    cmd = ["ansible-playbook", "-i", inv_path, playbook_rel_path]
    if extravars:
        for k, v in extravars.items():
            cmd += ["-e", f"{k}={v}"]
    subprocess.run(cmd, check=True)

def _ansible_get_stdout(inv_path: str, cmdline: str) -> str:
    # Ejecuta un ad-hoc con become y devuelve la última línea no vacía
    out = subprocess.check_output([
        "ansible", "-i", inv_path, "target",
        "-b",                    # become
        "-m", "shell",
        "-a", cmdline,
    ], text=True)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return lines[-1] if lines else ""

def add_wg_peer(server_ip: str, ssh_user: str, peer_pubkey: str, client_address: str, ssh_password: str | None = None):
    """
      1) Intenta clave -> add_peer.yml
      2) Si Permission denied y hay ssh_password:
           - bootstrap_add_key.yml  -> conexión por password
           - reintento add_peer.yml -> con clave
      3) Devuelve server_public_key
    """
    # Conexión por CLAVE
    inv_key = _write_temp_inventory(
        server_ip, ssh_user,
        extra={
            "ansible_ssh_private_key_file": SSH_KEY_PATH,
            # se hace por ssh por defecto
        },
    )

    try:
        _run_playbook(inv_key, "deploy/ansible/add_peer.yml", {
            "wg_port": WG_PORT,
            "peer_pubkey": peer_pubkey,
            "client_address": client_address,
        })
    except subprocess.CalledProcessError as e:
        err = str(e)
        needs_bootstrap = ("Permission denied" in err or "UNREACHABLE" in err) and ssh_password
        if not needs_bootstrap:
            raise

        # Inventario para conexión por PASSWORD (paramiko)
        inv_pw = _write_temp_inventory(
            server_ip, ssh_user,
            extra={"ansible_connection": "paramiko", "ansible_password": ssh_password}
        )
        # 2_A Bootstrap -> instala clave pública del controlador en authorized_keys
        _run_playbook(inv_pw, "deploy/ansible/bootstrap_add_key.yml", {})

        # 2_B Hacer reintento con clave
        _run_playbook(inv_key, "deploy/ansible/add_peer.yml", {
            "wg_port": WG_PORT,
            "peer_pubkey": peer_pubkey,
            "client_address": client_address,
        })

    # 3 Clave pública del servidor


    try:
        server_pub = _ansible_get_stdout(inv_key, "wg show wg0 public-key")
        if not server_pub or server_pub.lower().startswith("wg:"):
            raise RuntimeError("wg show fallback")
    except Exception:
        # Fallback: derivarla desde la privada si tu rol la guarda ahí
        server_pub = _ansible_get_stdout(inv_key, "wg pubkey < /etc/wireguard/server_private.key")

    if not server_pub:
        raise RuntimeError("No pude obtener la clave pública del servidor")

    return server_pub
