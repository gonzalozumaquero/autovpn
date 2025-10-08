# deploy/api/routers/install.py
import asyncio
import json
import os
import shlex
import stat
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from fastapi.responses import FileResponse
from pathlib import Path
import asyncio, tempfile, os, stat, uuid


# ===== Pydantic compat v1/v2 =====
try:
    from pydantic import BaseModel, Field, ConfigDict
    PydV2 = True
except Exception:  # v1
    from pydantic import BaseModel, Field
    PydV2 = False

# YAML (para group_vars)
try:
    import yaml
except Exception:
    yaml = None  # si falta, fallaremos con mensaje claro

router = APIRouter()

# ===== Rutas (en el contenedor) =====
BASE_DIR = Path(__file__).resolve().parents[1]      # /app
ANSIBLE_DIR = BASE_DIR / "ansible"
INV_DIR = ANSIBLE_DIR / "inventories"
GV_DIR = ANSIBLE_DIR / "group_vars"

PLAY_DEPLOY = ANSIBLE_DIR / "site-deploy.yml"
PLAY_STACK = ANSIBLE_DIR / "site-stack.yml"

RUNS_DIR = BASE_DIR / ".runs"
RUNS_DIR.mkdir(exist_ok=True)


# =========================
# Modelos (Pydantic)
# =========================

class AllowExtraModel(BaseModel):
    if PydV2:
        model_config = ConfigDict(extra="allow")
    else:
        class Config:
            extra = "allow"


class SSHConfig(AllowExtraModel):
    elastic_ip: str
    user: str = "ubuntu"
    ssh_port: int = 22
    pem: Optional[str] = Field(None, description="Contenido PEM (texto)")
    ssh_password: Optional[str] = Field(None, description="Password SSH (si no hay PEM)")


class TransportUdp2Raw(AllowExtraModel):
    enabled: bool = False
    password: Optional[str] = None
    mtu: Optional[int] = None


class Transport(AllowExtraModel):
    mode: str = "auto"                     # "auto" | "manual"
    profile: str = "WG_UDP_51820"          # usado si mode == "manual"
    udp2raw: TransportUdp2Raw = TransportUdp2Raw()


class StackVars(AllowExtraModel):
    if PydV2:
        model_config = ConfigDict(extra='allow')
    else:
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
    # Enviadas por el frontend dentro de vars:
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None


class InstallConfig(AllowExtraModel):
    if PydV2:
        model_config = ConfigDict(extra='allow')
    else:
        class Config:
            extra = 'allow'

    ssh: SSHConfig
    vars: StackVars
    transport: Optional[Transport] = None
    # retro-compat si vinieran arriba por error:
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    vault_password: Optional[str] = None


# =========================
# Utilidades
# =========================

def _write_secure(path: Path, content: str, mode: int = 0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)


async def _run_stream(cmd: list[str]) -> AsyncGenerator[str, None]:
    """
    Ejecuta un comando y emite la salida línea a línea (merge stdout/stderr).
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


def _require_yaml():
    if yaml is None:
        raise HTTPException(500, "Falta dependencia PyYAML en la imagen del backend (instala 'pyyaml').")


def next_temp_id() -> str:
    import uuid
    return str(uuid.uuid4())


# =========================
# Endpoints
# =========================
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
import paramiko, tempfile, os

CERT_PATH = "/opt/autovpn/caddy_data/caddy/pki/authorities/local/root.crt"

class SSHCreds(BaseModel):
    elastic_ip: str = Field(..., description="IP/Elastic IP del servidor")
    user: str = Field("ubuntu", description="Usuario SSH")
    ssh_port: int = Field(22, description="Puerto SSH")
    pem: str | None = Field(None, description="Contenido PEM (opcional)")
    ssh_password: str | None = Field(None, description="Contraseña SSH (opcional)")

class DownloadCertRequest(BaseModel):
    ssh: SSHCreds

def _connect(ssh: SSHCreds) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kwargs = dict(
        hostname=ssh.elastic_ip,
        username=ssh.user,
        port=ssh.ssh_port,
        allow_agent=False,
        look_for_keys=False,
        banner_timeout=10,
        auth_timeout=15,
        timeout=15,
    )
    tmp_key_path = None
    try:
        if ssh.pem:
            # Guardar PEM a un fichero temporal con permisos 0600
            tf = tempfile.NamedTemporaryFile("w", delete=False)
            tf.write(ssh.pem.strip() + "\n")
            tf.flush()
            tf.close()
            tmp_key_path = tf.name
            os.chmod(tmp_key_path, 0o600)
            connect_kwargs["key_filename"] = tmp_key_path
        elif ssh.ssh_password:
            connect_kwargs["password"] = ssh.ssh_password
        else:
            raise HTTPException(status_code=400, detail="Debes proporcionar pem o ssh_password.")

        client.connect(**connect_kwargs)
        return client
    except Exception:
        # Limpia el fichero temporal si lo hubo
        if tmp_key_path and os.path.exists(tmp_key_path):
            try: os.remove(tmp_key_path)
            except: pass
        raise
    finally:
        # Guarda la ruta en el propio objeto para borrarla tras el uso (feíllo pero práctico)
        ssh._tmp_key_path = tmp_key_path  # type: ignore[attr-defined]

def _cleanup_keyfile(ssh: SSHCreds):
    tmp = getattr(ssh, "_tmp_key_path", None)
    if tmp and os.path.exists(tmp):
        try: os.remove(tmp)
        except: pass

@router.post("/install/download-cert")
def download_cert(req: DownloadCertRequest):
    """
    Descarga la CA local de Caddy desde el servidor remoto vía SSH.
    Devuelve 'root.crt' como attachment.
    """
    ssh = req.ssh
    client = None
    try:
        client = _connect(ssh)

        # 1) Intento sin interacción (sudo -n). Requiere NOPASSWD.
        cmd = f"sudo -n cat {CERT_PATH}"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read()
        err = stderr.read().decode(errors="ignore")

        # 2) Si sudo pide password y tenemos ssh_password, reintenta con -S metiendo la pass por stdin
        if rc != 0 and ("a password is required" in err or "password is required" in err or "permission denied" in err.lower()):
            if ssh.ssh_password:
                cmd2 = f"sudo -S -p '' cat {CERT_PATH}"
                stdin2, stdout2, stderr2 = client.exec_command(cmd2, get_pty=True, timeout=20)
                # Pasar la contraseña a sudo
                stdin2.write(ssh.ssh_password + "\n")
                stdin2.flush()
                rc = stdout2.channel.recv_exit_status()
                out = stdout2.read()
                err = stderr2.read().decode(errors="ignore")

        if rc != 0 or not out:
            raise HTTPException(status_code=500, detail=f"No se pudo leer el certificado: {err.strip() or 'error desconocido'}")

        # Entregar como descarga
        headers = {"Content-Disposition": 'attachment; filename="root.crt"'}
        # application/x-x509-ca-cert o application/x-pem-file; cualquiera funciona
        return Response(content=out, media_type="application/x-x509-ca-cert", headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo SSH/descarga: {str(e)}")
    finally:
        _cleanup_keyfile(ssh)
        if client:
            try: client.close()
            except: pass














@router.post("/install/check-ssh")
async def check_ssh(ssh: SSHConfig):
    """
    Probar SSH con puerto y password o PEM.
    - PEM: usa openssh-client
    - Password: intenta Paramiko; si no está disponible, intenta sshpass.
    """
    if not ssh.pem and not ssh.ssh_password:
        raise HTTPException(400, "Debe enviarse 'pem' o 'ssh_password'")

    if ssh.pem:
        # ---- Clave PEM con ssh ----
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(ssh.pem)
            pem_path = f.name
        os.chmod(pem_path, stat.S_IRUSR | stat.S_IWUSR)
        try:
            cmd = [
                "ssh",
                "-p", str(ssh.ssh_port),
                "-i", pem_path,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=8",
                f"{ssh.user or 'ubuntu'}@{ssh.elastic_ip}",
                "echo ok"
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            if proc.returncode != 0:
                msg = (err or out or b"").decode("utf-8", "ignore").strip()
                raise HTTPException(400, f"SSH failed: {msg}")
            return {"ok": True, "stdout": (out or b"").decode("utf-8", "ignore").strip()}
        finally:
            try:
                os.unlink(pem_path)
            except Exception:
                pass

    # ---- Password: Paramiko -> fallback sshpass ----
    else:
        # 1) Paramiko (python puro)
        try:
            import paramiko  # type: ignore
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
            try:
                cli.close()
            except Exception:
                pass
            return {"ok": True, "stdout": raw_out.decode("utf-8", "ignore").strip()}
        except ModuleNotFoundError:
            # 2) sshpass si no hay paramiko
            cmd = [
                "sshpass", "-p", ssh.ssh_password or "",
                "ssh",
                "-p", str(ssh.ssh_port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=8",
                f"{ssh.user or 'ubuntu'}@{ssh.elastic_ip}",
                "echo ok"
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            out, _ = await proc.communicate()
            if proc.returncode != 0:
                raise HTTPException(400, f"SSH failed: {(out or b'').decode('utf-8','ignore').strip()}")
            return {"ok": True, "stdout": (out or b"").decode("utf-8", "ignore").strip()}
        except Exception as e:
            raise HTTPException(400, f"SSH failed: {e}")


@router.post("/install/config")
async def write_config(cfg: InstallConfig, request: Request):
    """
    Genera:
      - inventories/cloud.ini  (con [cloud] y vars; PEM placeholder o password placeholder)
      - group_vars/cloud.yml   (todas las vars, incl. admin_* y transport)
    """
    _require_yaml()

    # 1) Validar admin creds (admite en cfg.vars.* o a nivel raíz)
    try:
        vars_dict = cfg.vars.model_dump() if PydV2 else cfg.vars.dict()
    except Exception:
        vars_dict = {}

    body = await request.json()
    raw_vars = body.get("vars", {}) or {}

    admin_email = vars_dict.get("admin_email") or body.get("admin_email") or raw_vars.get("admin_email")
    admin_password = vars_dict.get("admin_password") or body.get("admin_password") or raw_vars.get("admin_password")

    if not admin_email or not admin_password:
        raise HTTPException(400, "Faltan admin_email y admin_password (en vars o a nivel raíz)")

    # 2) INVENTARIO
    inv_lines = [
        "[cloud]",
        "srv",
        "",
        "[cloud:vars]",
        f"ansible_host={cfg.ssh.elastic_ip}",
        f"ansible_user={cfg.ssh.user or 'ubuntu'}",
        f"ansible_port={cfg.ssh.ssh_port}",
        'ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"',
        "ansible_become=true",
        "ansible_python_interpreter=/usr/bin/python3",
    ]

    if cfg.ssh.pem:
        inv_lines.append("ansible_connection=ssh")
        inv_lines.append("ansible_ssh_private_key_file={PEM_PATH}")
    elif cfg.ssh.ssh_password:
        inv_lines.append("ansible_connection=ssh")
        inv_lines.append("ansible_password={SSH_PASSWORD_PLACEHOLDER}")
    else:
        raise HTTPException(400, "Falta credencial SSH (pem o ssh_password)")

    _write_secure(INV_DIR / "cloud.ini", "\n".join(inv_lines) + "\n", 0o600)

    # 3) GROUP_VARS (YAML completo)
    gv_data = {
        "use_internal_tls": bool(cfg.vars.use_internal_tls),
        "wg_public_host": cfg.vars.wg_public_host,
        "wg_port": int(cfg.vars.wg_port),
        "wg_subnet": cfg.vars.wg_subnet,
        "wg_dns": cfg.vars.wg_dns,
        "jwt_secret": cfg.vars.jwt_secret,
        "timezone": cfg.vars.timezone,
        # admin en claro (hash se deriva en Ansible)
        "admin_email": admin_email,
        "admin_password": admin_password,
    }

    # Transporte (si fue enviado por el frontend)
    if cfg.transport:
        try:
            transport_dict = cfg.transport.model_dump() if PydV2 else cfg.transport.dict()
        except Exception:
            transport_dict = {}
        gv_data["transport"] = transport_dict

    GV_DIR.mkdir(parents=True, exist_ok=True)
    _write_secure(GV_DIR / "cloud.yml", yaml.safe_dump(gv_data, sort_keys=False), 0o600)

    return {"ok": True}


@router.post("/install/run")
async def run_install(cfg: InstallConfig):
    """
    Prepara inventario temporal sustituyendo placeholders y lanza los playbooks:
      1) Sustituye {PEM_PATH} si hay PEM (guardada temporalmente).
      2) Sustituye {SSH_PASSWORD_PLACEHOLDER} si hubo password.
      3) Devuelve run_id para /install/logs/{run_id}.
    """
    inv_src = INV_DIR / "cloud.ini"
    if not inv_src.exists():
        raise HTTPException(400, "cloud.ini no existe. Llama primero a /install/config")

    inv_txt = inv_src.read_text(encoding="utf-8")
    temp_files: list[str] = []

    if cfg.ssh.pem:
        pem_file = os.path.join(tempfile.gettempdir(), f"autovpn_{next_temp_id()}.pem")
        Path(pem_file).write_text(cfg.ssh.pem, encoding="utf-8")
        os.chmod(pem_file, 0o600)
        if "{PEM_PATH}" not in inv_txt:
            raise HTTPException(400, "Inventario no esperaba PEM. Repite /install/config aportando pem.")
        inv_txt = inv_txt.replace("{PEM_PATH}", pem_file)
        temp_files.append(pem_file)
    elif cfg.ssh.ssh_password:
        if "{SSH_PASSWORD_PLACEHOLDER}" not in inv_txt:
            raise HTTPException(400, "Inventario no preparado para password. Repite /install/config en modo password.")
        inv_txt = inv_txt.replace("{SSH_PASSWORD_PLACEHOLDER}", cfg.ssh.ssh_password or "")
    else:
        raise HTTPException(400, "Falta credencial SSH (pem o ssh_password)")

    # Inventario TEMPORAL para esta ejecución
    inv_tmp_fd, inv_tmp_path = tempfile.mkstemp(suffix=".ini", prefix="inv_run_")
    with os.fdopen(inv_tmp_fd, "w", encoding="utf-8") as f:
        f.write(inv_txt)
    os.chmod(inv_tmp_path, 0o600)
    temp_files.append(inv_tmp_path)

    run_id = next_temp_id()
    (RUNS_DIR / f"{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "elastic_ip": cfg.ssh.elastic_ip,
                "inv": inv_tmp_path,
                "temps": temp_files,
                "ts": datetime.utcnow().isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return {"run_id": run_id}


@router.get("/install/logs/{run_id}")
async def stream_logs(run_id: str):
    """
    Stream de logs (SSE) ejecutando los dos playbooks con el inventario temporal.
    Limpia los temporales al terminar.
    """
    meta_path = RUNS_DIR / f"{run_id}.json"
    if not meta_path.exists():
        raise HTTPException(404, "run_id no encontrado")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    inv_tmp_path = meta["inv"]
    temp_files = meta.get("temps", [])
    elastic_ip = meta.get("elastic_ip")

    async def _stream():
        try:
            # DEPLOY
            yield "event: info\ndata: Starting deploy...\n\n"
            cmd1 = ["ansible-playbook", "-i", inv_tmp_path, str(PLAY_DEPLOY)]
            async for line in _run_stream(cmd1):
                yield f"data: {line}\n\n"

            # STACK
            yield "event: info\ndata: Starting stack...\n\n"
            cmd2 = ["ansible-playbook", "-i", inv_tmp_path, str(PLAY_STACK)]
            async for line in _run_stream(cmd2):
                yield f"data: {line}\n\n"

            url = f"https://{elastic_ip}/"
            (RUNS_DIR / f"{run_id}.done").write_text(json.dumps({"url": url}), encoding="utf-8")
            yield f"event: done\ndata: {url}\n\n"
        finally:
            # limpieza de temporales
            for p in temp_files:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    return StreamingResponse(_stream(), media_type="text/event-stream")

