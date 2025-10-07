import os, subprocess, base64
import docker,json
from typing import Tuple

WG_CONTAINER = os.getenv("WG_CONTAINER_NAME", "wireguard")
WG_SUBNET = os.getenv("WG_SUBNET", "10.13.13.0/24")
WG_DNS = os.getenv("WG_DNS", "10.13.13.1")
WG_HOST = os.getenv("WG_HOST", "127.0.0.1")
WG_PORT = int(os.getenv("WG_PORT", "51820"))

def _run_in_wireguard(cmd: list[str]) -> Tuple[int,str,str]:
    # usa Docker SDK para exec dentro del contenedor wireguard
    client = docker.from_env()
    c = client.containers.get(WG_CONTAINER)
    exec_res = c.exec_run(cmd, stdout=True, stderr=True)
    code = exec_res.exit_code
    out = exec_res.output.decode() if isinstance(exec_res.output, (bytes,bytearray)) else str(exec_res.output)
    return code, out, ""

def gen_keypair() -> Tuple[str,str]:
    code, priv, _ = _run_in_wireguard(["bash","-lc","wg genkey"])
    if code != 0: raise RuntimeError("wg genkey failed")
    priv = priv.strip()
    code, pub, _ = _run_in_wireguard(["bash","-lc",f"printf '%s' '{priv}' | wg pubkey"])
    if code != 0: raise RuntimeError("wg pubkey failed")
    return priv, pub.strip()

def server_public_key() -> str:
    code, out, _ = _run_in_wireguard(["bash","-lc","wg show wg0 public-key"])
    if code != 0: raise RuntimeError("wg show public-key failed")
    return out.strip()

def allocate_ip(next_host:int) -> str:
    # súper simple: asume /24 y que .1 es el servidor
    base = ".".join(WG_SUBNET.split("/")[0].split(".")[:3])
    return f"{base}.{next_host}/32"

def add_peer(server_pub: str, client_pub: str, client_ip_cidr: str):
    code, out, err = _run_in_wireguard(["bash","-lc",f"wg set wg0 peer {client_pub} allowed-ips {client_ip_cidr}"])
    if code != 0: raise RuntimeError(f"wg set failed: {out or err}")

def remove_peer(client_pub: str):
    _run_in_wireguard(["bash","-lc",f"wg set wg0 peer {client_pub} remove"])

def render_client_conf(client_priv: str, client_ip_cidr: str, server_pub: str) -> str:
    return f"""[Interface]
PrivateKey = {client_priv}
Address = {client_ip_cidr}
DNS = {WG_DNS}

[Peer]
PublicKey = {server_pub}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {WG_HOST}:{WG_PORT}
PersistentKeepalive = 25
"""
def docker_client():
    return docker.from_env()

def container_control(action: str) -> dict:
    cli = docker_client()
    c = cli.containers.get(WG_CONTAINER)
    if action == "start":
        c.start()
    elif action == "stop":
        c.stop(timeout=10)
    elif action == "restart":
        c.restart(timeout=10)
    else:
        raise ValueError("invalid action")
    c.reload()
    return {"name": c.name, "status": c.status}

def wg_show() -> dict:
    cli = docker_client()
    c = cli.containers.get(WG_CONTAINER)
    exec_res = c.exec_run(["bash","-lc","wg show all dump || wg show"], stdout=True, stderr=True)
    out = exec_res.output.decode(errors="ignore")
    # Si está vacío o error, devolver status del contenedor
    return {"raw": out.strip()}
