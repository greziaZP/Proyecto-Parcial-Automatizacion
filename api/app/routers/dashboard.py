from typing import List, Dict, Any
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/incidencias/{aula_id}")
async def listar_incidencias(aula_id: str) -> List[Dict[str, Any]]:
    """
    Listar la asistencia del día para directores y profesores.
    A futuro: Consulta directa a PostgreSQL (SQLAlchemy).
    No interviene IA para esta lectura.
    """
    return [
        {
            "alumno_id": "A001",
            "nombre": "Juan Pérez",
            "estado": "Presente",
            "hora_marcacion": "07:55 AM"
        },
        {
            "alumno_id": "A002",
            "nombre": "Ana Gómez",
            "estado": "Alerta Roja (Falta Injustificada)",
            "hora_marcacion": None
        },
        {
            "alumno_id": "A003",
            "nombre": "Luis Alberto",
            "estado": "Justificado (Pre-aprobado)",
            "hora_marcacion": None
        }
    ]

@router.get("/citaciones")
async def listar_citaciones() -> List[Dict[str, Any]]:
    """
    Listar las reuniones agendadas autónomamente por la IA.
    A futuro: Consulta directa a PostgreSQL para listar citas generadas por el Agente.
    """
    return [
        {
            "citacion_id": "C-1001",
            "alumno_id": "A192",
            "motivo": "Reincidencia de faltas injustificadas (3 veces en el último mes)",
            "departamento": "Psicopedagogía",
            "fecha_reunion": "2026-05-20T10:00:00Z",
            "agendado_por": "IA Autónoma"
        },
        {
            "citacion_id": "C-1002",
            "alumno_id": "A043",
            "motivo": "Patrón de llegadas tardías detectado",
            "departamento": "Dirección Académica",
            "fecha_reunion": "2026-05-21T08:30:00Z",
            "agendado_por": "IA Autónoma"
        }
    ]
