# deploy/api/routers/install.py
import asyncio
import json
import os
import shlex
import stat
import tempfile
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse, PlainTextResponse, FileResponse
from datetime import datetime

from typing import Optional
from pydantic import BaseModel, Field
try:
    from pydantic import ConfigDict
    PydV2 = True
except Exception:
    PydV2 = False


router = APIRouter()

# Raíz de trabajo dentro del contenedor (WORKDIR /app)
BASE_DIR = Path(__file__).resolve().parents[1]   # -> /app
ANSIBLE_DIR = BASE_DIR / "ansible"
INV_DIR = ANSIBLE_DIR / "inventories"
GV_DIR  = ANSIBLE_DIR / "group_vars"

# Playbooks
PLAY_DEPLOY = ANSIBLE_DIR / "site-deploy.yml"
PLAY_STACK  = ANSIBLE_DIR / "site-stack.yml"

# Plantillas .example
INV_EXAMPLE = INV_DIR / "cloud.ini.example"
GV_EXAMPLE  = GV_DIR  / "cloud.yml.example"

# Carpeta para metadatos de ejecuciones
RUNS_DIR = BASE_DIR / ".runs"
RUNS_DIR.mkdir(exist_ok=True)


# --------------------------
# Modelos (esquemas)
# --------------------------

from typing import Optional

class SSHConfig(BaseModel):
    elastic_ip: str
    user: str = "ubuntu"
    ssh_port: int = 22
    pem: Optional[str] = Field(None, description="Contenido PEM (texto)")
    ssh_password: Optional[str] = Field(None, description="Password SSH (si no hay PEM)")

class StackVars(BaseModel):
    # Permite campos extra (admin_email/admin_password) sin reventar
    if PydV2:
        # Pydantic v2
        model_config = ConfigDict(extra='allow')
    else:
        # Pydantic v1
        class Config:
            extra = 'allow'

    use_internal_tls: bool = True
    wg_public_host: str
    wg_port: int = 51820
    wg_subnet: str = "10.13.13.0/24"
    wg_dns: str = "1.1.1.1"
    jwt_secret: str
    timezone: str = "Europe/Madrid"
    s3_bucket: str = ""
    # explícitos y opcionales, por si tu UI los manda en vars
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None


class InstallConfig(BaseModel):
    ssh: SSHConfig
    vars: StackVars
    admin_email: Optional[str] = None   # fallback si vienen a nivel raíz
    admin_password: Optional[str] = None
    vault_password: Optional[str] = None

# --------------------------
# Utilidades
# --------------------------

def _write_secure(path: Path, content: str, mode: int = 0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)

async def _run_stream(cmd: list[str]) -> AsyncGenerator[str, None]:
    """
    Ejecuta un comando y emite la salida línea a línea (universal newlines).
    """
    proc = await asyncio.create_subprocess_exec(
    *cmd,
    cwd=str(ANSIBLE_DIR),                       
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.STDOUT
    )
    assert proc.stdout is not None
    async for raw in proc.stdout:
        yield raw.decode(errors="ignore").rstrip("\n")
    await proc.wait()

def _render_from_example(example_path: Path, replacements: dict[str, str]) -> str:
    if not example_path.exists():
        raise FileNotFoundError(f"Falta plantilla: {example_path}")
    txt = example_path.read_text(encoding="utf-8")
    for k, v in replacements.items():
        txt = txt.replace(k, v)
    return txt


# --------------------------
# Endpoints
# --------------------------

@router.post("/install/check-ssh")
async def check_ssh(ssh: SSHConfig):
    if not ssh.pem and not ssh.ssh_password:
        raise HTTPException(400, "Debe enviarse 'pem' o 'ssh_password'")
    if ssh.pem:
        import shlex, stat, tempfile, os, asyncio
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(ssh.pem)
            pem_path = f.name
        os.chmod(pem_path, stat.S_IRUSR | stat.S_IWUSR)
        try:
            cmd = (
                f"ssh -p {ssh.ssh_port} "
                f"-i {shlex.quote(pem_path)} "
                "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                "-o ConnectTimeout=8 "
                f"{ssh.user or 'ubuntu'}@{ssh.elastic_ip} echo ok"
            )
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            if proc.returncode != 0:
                msg = (err or out or b"").decode("utf-8", "ignore").strip()
                raise HTTPException(400, f"SSH failed: {msg}")
            raw_out = out  # bytes
        finally:
            try: os.unlink(pem_path)
            except: pass

    # --- MODO PASSWORD (paramiko) ---
    else:
        import paramiko
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            cli.connect(
                hostname=ssh.elastic_ip,
                port=ssh.ssh_port,
                username=ssh.user or "ubuntu",
                password=ssh.ssh_password,
                look_for_keys=False,
                allow_agent=False,
                timeout=8,
            )
            _stdin, _stdout, _stderr = cli.exec_command("echo ok")
            raw_out = _stdout.read()  # bytes
        except Exception as e:
            raise HTTPException(400, f"SSH failed: {e}")
        finally:
            try: cli.close()
            except: pass

    # --- Normalizar salida (bytes|bytearray -> str) y responder ---
    text = raw_out.decode("utf-8", "ignore") if isinstance(raw_out, (bytes, bytearray)) else str(raw_out)
    return {"ok": True, "stdout": text.strip()}


@router.post("/install/config")
async def write_config(cfg: InstallConfig, request: Request):
    # cuerpo crudo por si Pydantic tiró keys extra
    body = await request.json()
    raw_vars = body.get("vars", {}) or {}

    # Soporta ambas rutas: en cfg.vars (si el modelo las tiene) o en el JSON crudo
    try:
        vars_dict = cfg.vars.model_dump()  # pydantic v2
    except AttributeError:
        vars_dict = cfg.vars.dict()        # pydantic v1

    admin_email = vars_dict.get("admin_email") or body.get("admin_email") or raw_vars.get("admin_email")
    admin_password = vars_dict.get("admin_password") or body.get("admin_password") or raw_vars.get("admin_password")

    if not admin_email or not admin_password:
        raise HTTPException(400, "Faltan admin_email y admin_password (en vars o a nivel raíz)")

    # 1) INVENTARIO
    if cfg.ssh.pem:
        inv_text = (
            "[cloud]\n"                                                    # ← antes ponías [target]
            f"srv ansible_host={cfg.ssh.elastic_ip} "
            f"ansible_user={cfg.ssh.user or 'ubuntu'} "
            'ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"\n\n'
            "[cloud:vars]\n"                                              # ← antes [target:vars]
            "ansible_become=true\n"
            "ansible_python_interpreter=/usr/bin/python3\n"
            f"ansible_port={cfg.ssh.ssh_port}\n"
            f'ansible_ssh_private_key_file={{PEM_PATH}}\n'
            )

    else:
        inv_text = (
            "[cloud]\n"
            f"srv ansible_host={cfg.ssh.elastic_ip} "
            f"ansible_user={cfg.ssh.user or 'ubuntu'} "
            'ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"\n\n'
            "[cloud:vars]\n"
            "ansible_become=true\n"
            "ansible_connection=paramiko\n"
            "ansible_python_interpreter=/usr/bin/python3\n"
            f"ansible_port={cfg.ssh.ssh_port}\n"
            "ansible_password={SSH_PASSWORD_PLACEHOLDER}\n"
        )   

    _write_secure(INV_DIR / "cloud.ini", inv_text, 0o600)

    # 2) GROUP_VARS (inyecta campos; si tu .example ya trae claves, las reemplaza)
    gv_path = GV_DIR / "cloud.yml"
    desired = {
        "wg_public_host": cfg.vars.wg_public_host,
        "wg_port": cfg.vars.wg_port,
        "wg_subnet": cfg.vars.wg_subnet,
        "wg_dns": cfg.vars.wg_dns,
        "jwt_secret": cfg.vars.jwt_secret,
        "timezone": cfg.vars.timezone,
        "use_internal_tls": "true" if cfg.vars.use_internal_tls else "false",
        "admin_email": admin_email,
        "admin_password": admin_password,
    }

    # Si tienes un .example, puedes empezar de él:
    base_text = ""
    if GV_EXAMPLE.exists():
        base_text = GV_EXAMPLE.read_text(encoding="utf-8")

    # reescritura simple línea a línea (como ya hacías)
    lines = []
    present = set()
    for line in base_text.splitlines() if base_text else []:
        key = line.split(":")[0].strip() if ":" in line else ""
        if key in desired:
            val = desired[key]
            line = f'{key}: "{val}"' if isinstance(val, str) and key != "use_internal_tls" else f"{key}: {val}"
            present.add(key)
        lines.append(line)

    # añade las que falten
    for k, v in desired.items():
        if k not in present:
            if isinstance(v, str) and k != "use_internal_tls":
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f"{k}: {v}")

    _write_secure(gv_path, "\n".join(lines) + "\n", 0o600)

    return {"ok": True}

@router.post("/install/run")
async def run_install(cfg: InstallConfig):
    """
    1) Guarda el PEM de forma temporal.
    2) Inserta su ruta en inventories/cloud.ini (sustituyendo {PEM_PATH}).
    3) Devuelve run_id para suscribirse a /install/logs/{run_id}.
    """
    inv_path = INV_DIR / "cloud.ini"
    if not inv_path.exists():
        raise HTTPException(400, "cloud.ini no existe. Llama primero a /install/config")

    inv_txt = inv_path.read_text(encoding="utf-8")
    temp_files = []

    if cfg.ssh.pem:
        pem_file = str((tempfile.gettempdir() + f"/autovpn_{next_temp_id()}.pem"))
        Path(pem_file).write_text(cfg.ssh.pem, encoding="utf-8")
        os.chmod(pem_file, 0o600)
        inv_txt = inv_txt.replace("{PEM_PATH}", pem_file)
        temp_files.append(pem_file)
    else:
        if "{SSH_PASSWORD_PLACEHOLDER}" not in inv_txt:
            raise HTTPException(400, "Inventario no preparado para password. Repite /install/config en modo password.")
        inv_txt = inv_txt.replace("{SSH_PASSWORD_PLACEHOLDER}", cfg.ssh.ssh_password or "")

    inv_tmp_fd, inv_tmp_path = tempfile.mkstemp(suffix=".ini", prefix="inv_run_")
    with os.fdopen(inv_tmp_fd, "w", encoding="utf-8") as f:
        f.write(inv_txt)
    os.chmod(inv_tmp_path, 0o600)
    temp_files.append(inv_tmp_path)

    run_id = next_temp_id()
    (RUNS_DIR / f"{run_id}.json").write_text(
        json.dumps({"run_id": run_id, "elastic_ip": cfg.ssh.elastic_ip, "inv": inv_tmp_path, "temps": temp_files}),
        encoding="utf-8"
    )

    return {"run_id": run_id}

def next_temp_id() -> str:
    import uuid
    return str(uuid.uuid4())

@router.get("/install/logs/{run_id}")
async def stream_logs(run_id: str):
    meta = json.loads((RUNS_DIR / f"{run_id}.json").read_text(encoding="utf-8"))
    inv_tmp_path = meta["inv"]
    temp_files = meta.get("temps", [])
    elastic_ip = meta["elastic_ip"]

    async def _stream():
        try:
            yield "event: info\ndata: Starting deploy...\n\n"
            cmd1 = ["ansible-playbook", "-i", inv_tmp_path, str(PLAY_DEPLOY)]
            async for line in _run_stream(cmd1):
                yield f"data: {line}\n\n"

            yield "event: info\ndata: Starting stack...\n\n"
            cmd2 = ["ansible-playbook", "-i", inv_tmp_path, str(PLAY_STACK)]
            async for line in _run_stream(cmd2):
                yield f"data: {line}\n\n"

            url = f"https://{elastic_ip}/"
            (RUNS_DIR / f"{run_id}.done").write_text(json.dumps({"url": url}), encoding="utf-8")
            yield f"event: done\ndata: {url}\n\n"
        finally:
            for p in temp_files:
                try: os.unlink(p)
                except: pass

    return StreamingResponse(_stream(), media_type="text/event-stream")


#@router.get("/install/logs/{run_id}")
#async def stream_logs(run_id: str):
#    meta_path = RUNS_DIR / f"{run_id}.json"
#    if not meta_path.exists():
#        raise HTTPException(404, "run_id no encontrado")
#    meta = json.loads(meta_path.read_text(encoding="utf-8"))
#    pem_file = meta["pem"]
#    elastic_ip = meta["elastic_ip"]
#
#    log_path = RUNS_DIR / f"{run_id}.log"
#    log_path.parent.mkdir(parents=True, exist_ok=True)
#   async def _stream():
#        try:
#            # Abrimos el fichero una sola vez y escribimos en append
#            with open(log_path, "a", encoding="utf-8") as lf:
#
#                def emit(line: str) -> str:
#                    """Escribe al log y devuelve la misma línea para el SSE."""
#                    lf.write(line + "\n")
#                    lf.flush()
#                    return line
#
#                # DEPLOY
#                yield "event: info\ndata: Starting deploy...\n\n"
#                cmd1 = ["ansible-playbook", "-i", str(INV_DIR / "cloud.ini"), str(PLAY_DEPLOY)]
#                async for line in _run_stream(cmd1):
#                    yield f"data: {emit(line)}\n\n"
#
#                # STACK
#                yield "event: info\ndata: Starting stack...\n\n"
#                cmd2 = ["ansible-playbook", "-i", str(INV_DIR / "cloud.ini"), str(PLAY_STACK)]
#                async for line in _run_stream(cmd2):
#                    yield f"data: {emit(line)}\n\n"
#
#            # END (fuera del with, pero aún dentro del try)
#            url = f"https://{elastic_ip}/"
#            (RUNS_DIR / f"{run_id}.done").write_text(
#                json.dumps({"url": url, "finished_at": datetime.utcnow().isoformat()}),
#                encoding="utf-8"
#            )
#            yield f"event: done\ndata: {url}\n\n"
#
#        finally:
#            # limpiar PEM temporal
#            try:
#                os.unlink(pem_file)
#            except Exception:
#                pass
#
#    return StreamingResponse(_stream(), media_type="text/event-stream")


class SSHConfig(BaseModel):
    elastic_ip: str
    user: str = "ubuntu"
    ssh_port: int = 22
    pem: Optional[str] = None
    ssh_password: Optional[str] = None

class StackVars(BaseModel):
    # Permite campos que aún no estén en el modelo (retrocompatible)
    model_config = ConfigDict(extra='allow')

    use_internal_tls: bool = True
    wg_public_host: str
    wg_port: int = 51820
    wg_subnet: str = "10.13.13.0/24"
    wg_dns: str = "1.1.1.1"
    jwt_secret: str
    timezone: str = "Europe/Madrid"
    s3_bucket: str = ""
    # Si puedes, añádelos explícitos también:
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None

class InstallConfig(BaseModel):
    ssh: SSHConfig
    vars: StackVars
    # Retrocompatibilidad: por si el cliente los manda arriba por error
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    vault_password: Optional[str] = None



# ========== LOGS =============

from fastapi.responses import PlainTextResponse, FileResponse

@router.get("/install/runs")
def list_runs():
    items = []
    for p in sorted(RUNS_DIR.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({
            "run_id": p.stem,
            "size": p.stat().st_size,
            "mtime": int(p.stat().st_mtime),
        })
    return {"runs": items}

@router.get("/install/logs/{run_id}/raw", response_class=PlainTextResponse)
def read_log_raw(run_id: str):
    log_path = RUNS_DIR / f"{run_id}.log"
    if not log_path.exists():
        raise HTTPException(404, "Log no encontrado")
    return log_path.read_text(encoding="utf-8")

@router.get("/install/logs/{run_id}/download")
def download_log(run_id: str):
    log_path = RUNS_DIR / f"{run_id}.log"
    if not log_path.exists():
        raise HTTPException(404, "Log no encontrado")
    return FileResponse(path=log_path, media_type="text/plain", filename=f"autovpn-{run_id}.log")

