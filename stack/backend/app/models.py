from sqlmodel import SQLModel, Field, UniqueConstraint
from typing import Optional
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    totp_secret: Optional[str] = None
    totp_enabled: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Peer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    name: str
    client_private: str
    client_public: str
    client_ip: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = None

class Settings(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("k"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    k: str
    v: str

