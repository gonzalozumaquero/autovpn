# schemas.py
from pydantic import BaseModel, Field

# --- ya existentes ---
class WGParamsReq(BaseModel):
    peer_name: str
    peer_public_key: str
    server_hint: str
    ssh_user: str | None = None
    ssh_password: str | None = None

class WGParamsResp(BaseModel):
    endpoint: str
    server_public_key: str
    dns: str
    allowed_ips: str
    client_address: str

# --- nuevos para installer ---
class SSHConfig(BaseModel):
    elastic_ip: str
    pem: str = Field(..., description="Contenido PEM en texto")
    user: str = "ubuntu"

class StackVars(BaseModel):
    use_internal_tls: bool = True
    wg_public_host: str
    wg_port: int = 51820
    wg_subnet: str = "10.13.13.0/24"
    wg_dns: str = "1.1.1.1"
    jwt_secret: str
    timezone: str = "Europe/Madrid"
    s3_bucket: str = ""

class InstallConfig(BaseModel):
    ssh: SSHConfig
    vars: StackVars
    vault_password: str | None = None

