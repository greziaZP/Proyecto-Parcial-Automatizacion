from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar los routers de la aplicación
from app.routers import asistencia, justificaciones
from app.routers.biometria import router_biometria
from app.routers.entities import router as router_entities
from app.routers.rekognition_asistencia import router as router_rekognition

app = FastAPI(
    title="API de Asistencia e Intervención Académica",
    description="Backend en FastAPI con soporte para Swarm de Agentes y RAG",
    version="1.0.0"
)

# Configuración básica de CORS para permitir peticiones del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir los routers estructurados
app.include_router(asistencia.router)
app.include_router(justificaciones.router)

# ── AWS Rekognition ──────────────────────────────────────────────────────────
app.include_router(router_biometria)      # POST /biometria/registrar
app.include_router(router_entities)       # GET  /alumnos | /cursos | /profesores
app.include_router(router_rekognition)    # POST /asistencia/registrar | /cerrar-jornada

@app.get("/")
async def root():
    return {"message": "Bienvenido a la API de Asistencia Inteligente"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
