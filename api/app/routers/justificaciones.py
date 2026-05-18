import logging
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form
from pydantic import BaseModel
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/justificaciones", tags=["Justificaciones"])

class PreFaltaRequest(BaseModel):
    alumno_id: str
    fecha_inicio: date
    fecha_fin: date
    motivo_texto: str

@router.post("/chat")
async def chat_justificacion(
    mensaje: str = Form(...),
    alumno_id: str = Form(...),
    incidencia_id: str = Form(...),
    adjunto: Optional[UploadFile] = File(None)
):
    """
    Chat interactivo del padre de familia con el agente.
    A futuro: El mensaje y adjunto pasarán por el Orquestador hacia 
    el Swarm de agentes LLM (OpenAI/Anthropic) para mutar el Shared State.
    """
    
    # Retorna un objeto JSON estructurado simulando la Memoria Compartida (Shared State)
    shared_state_mock = {
        "status": "success (Mocked mode)",
        "agentes_involucrados": ["Agente Recepcionista", "Agente Evaluador"],
        "estado_compartido": {
            "analisis_conductual": "El comportamiento histórico del alumno indica 95% de asistencia. Perfil confiable.",
            "resultado_rag_reglamento": "El reglamento permite hasta 3 faltas médicas justificadas por trimestre. Aplicable.",
            "dictamen_final": "Justificación aprobada por motivos de salud conforme al artículo 14."
        }
    }
    
    return shared_state_mock

@router.post("/pre-falta")
async def solicitar_pre_falta(request: PreFaltaRequest):
    """
    Formulario para que el padre solicite un permiso anticipado.
    A futuro: Consulta semántica en Base de Datos Vectorial (Qdrant/Milvus)
    e inserción a través de un servidor MCP local a PostgreSQL.
    """
    # Simulando acciones de agente evaluador y consulta a BD vectorial
    logger.info("Agente Evaluador: Consultando base de datos vectorial sobre historial y políticas...")
    logger.info("Agente Evaluador: Evaluación completada positivamente.")
    
    return {
        "status": "Permiso Pre-Aprobado por IA (Simulado)",
        "message": "El MCP de escritura se encargará de guardar este estado en la base de datos PostgreSQL cuando el servidor esté operativo.",
        "datos_procesados": request.model_dump()
    }
