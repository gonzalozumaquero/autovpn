from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import peers, status  # Se irán añadiendo más routers después

# PRIMERO: crear la instancia de la app
app = FastAPI(
    title="AutoVPN Backend",
    description="API para gestionar peers y configuración de servidores VPN personales",
    version="0.1.0"
)

# Middleware para permitir peticiones desde el frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # CAMBIAR EN PRODUCCIÓN
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rutas (endpoints)
app.include_router(peers.router, prefix="/peers", tags=["Peers"])
app.include_router(status.router, prefix="/status", tags=["Status"])

# Endpoint raíz de prueba
@app.get("/")
def root():
    return {"message": "AutoVPN API activa"}
