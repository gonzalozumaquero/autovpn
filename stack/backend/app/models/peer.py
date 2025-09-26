from pydantic import BaseModel

class PeerCreateRequest(BaseModel):
    name: str

class PeerConfigResponse(BaseModel):
    peer_id: str
    config: str

class PeerInfo(BaseModel):
    peer_id: str
    name: str
    created_at: str
