import json, ipaddress
from pathlib import Path

STATE_DIR = Path("/app/state")
STATE_FILE = STATE_DIR / "peers.json"
POOL_CIDR = ipaddress.ip_network("10.13.13.0/24")
SERVER_IP = ipaddress.ip_address("10.13.13.1")  # wg0 del servidor

def _load_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            if "allocated" not in data:
                data["allocated"] = {}
            return data
        except json.JSONDecodeError:
            # Si el archivo está corrupto o vacío, reinicia
            return {"allocated": {}}
    return {"allocated": {}}


def _save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def alloc_client_ip(peer_name: str) -> str:
    """ Devuelve 'x.x.x.x/32' sin colisión. """
    state = _load_state()
    used = {ipaddress.ip_network(v["address"]).network_address for v in state["allocated"].values()}
    used.add(SERVER_IP)

    for host in POOL_CIDR.hosts():
        if host == SERVER_IP:
            continue
        if host not in used:
            cidr = f"{host}/32"
            state["allocated"][peer_name] = {"address": cidr}
            _save_state(state)
            return cidr
    raise RuntimeError("No hay IPs libres en el pool 10.13.13.0/24")

def get_client_ip(peer_name: str) -> str:
    state = _load_state()
    if peer_name in state["allocated"]:
        return state["allocated"][peer_name]["address"]
    return alloc_client_ip(peer_name)

