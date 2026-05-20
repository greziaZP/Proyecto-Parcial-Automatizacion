import logging
from typing import Optional, List
from fastapi import APIRouter, File, UploadFile, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asistencia", tags=["Asistencia"])

class CierreRequest(BaseModel):
    aula_id: str
    fecha: str

@router.post("/marcar")
async def marcar_asistencia(
    aula_id: str = Form(...),
    imagen_base64: Optional[str] = Form(None),
    archivo: Optional[UploadFile] = File(None)
):
    """
    Simula la captura de imagen de la cámara de entrada.
    A futuro: Aquí se integrará AWS Rekognition procesando 'archivo' o 'imagen_base64'.
    """
    if not imagen_base64 and not archivo:
        return {"status": "error", "message": "Se requiere archivo de imagen o base64"}
    
    # Simulación de detección exitosa / Servicio inactivo
    # return {"status": "Service currently unavailable (Mocked mode)"}
    
    mock_alumnos_detectados = ["alumno_id_1", "alumno_id_2"]
    
    return {
        "status": "success",
        "message": "Asistencia registrada correctamente (Simulado)",
        "detectados": mock_alumnos_detectados
    }


@router.post("/cierre")
async def cierre_asistencia(request: CierreRequest):
    """
    Ejecución manual del cierre de jornada por parte del director.
    A futuro: Se conectará a PostgreSQL para verificar lista total vs presentes,
    y se invocará al sistema de eventos reales.
    """
    # Lógica simulada de diferencia matemática
    alumnos_totales = 30
    presentes = 25
    ausentes = alumnos_totales - presentes
    
    # Simula el disparo del Event Bus de Antigravity
    logger.info("Event Bus triggered for missing students")
    
    return {
        "status": "success",
        "message": "Cierre de jornada ejecutado correctamente (Simulado)",
        "detalles": {
            "aula_id": request.aula_id,
            "ausentes_totales": ausentes,
            "estado_generado": "Pendiente_Justificacion",
            "inasistencias_congeladas": ausentes
        }
    }
