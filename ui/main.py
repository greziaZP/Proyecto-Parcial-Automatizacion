"""
ui/main.py — Entry point de la app de UI.
=========================================
Sirve dashboard.py y asistencia.py como páginas web.

Ejecución:
    pip install fastapi uvicorn psycopg2-binary python-dotenv
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload

    → http://localhost:8080/           (Dashboard)
    → http://localhost:8080/asistencia (Toma de Asistencia)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard   import router as router_dashboard
from asistencia  import router as router_asistencia

app = FastAPI(
    title="UI — Asistencia Biométrica Narváez",
    description="Frontend Python del sistema de asistencia facial.",
    version="1.0.0",
    docs_url=None,   # sin /docs en la UI
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_dashboard)
app.include_router(router_asistencia)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
