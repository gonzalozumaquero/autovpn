from pydantic import BaseModel, Field

class WGParamsReq(BaseModel):
    peer_name: str = Field(..., min_length=1, max_length=64)
    peer_public_key: str = Field(..., min_length=40, max_length=120)
    server_hint: str = Field(..., description="IP o FQDN del servidor destino")
    ssh_user: str | None = None 
    ssh_password: str | None = Field(None, description="(Opcional) Password inicial para bootstrap")

class WGParamsResp(BaseModel):
    endpoint: str
    server_public_key: str
    dns: str
    allowed_ips: str
    client_address: str
