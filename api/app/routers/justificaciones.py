import logging
import uuid
from typing import Optional
from datetime import date
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.state.shared_state import SharedState
from app.agents.orquestador import OrquestadorAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/justificaciones", tags=["Justificaciones"])

executor = ThreadPoolExecutor(max_workers=4)


class PreFaltaRequest(BaseModel):
    alumno_id: str
    fecha_inicio: date
    fecha_fin: date
    motivo_texto: str


class ChatResponse(BaseModel):
    alumno_id: str
    tipo_flujo: str
    estado_actual: str
    analisis_conductual: Optional[str] = None
    resultado_rag_reglamento: Optional[str] = None
    dictamen_final: Optional[str] = None
    mcp_logs: list = []


def _ejecutar_swarm(state: SharedState, mensaje: str) -> SharedState:
    orquestador = OrquestadorAgent()
    return orquestador.ejecutar(state, mensaje)


@router.post("/chat", response_model=ChatResponse)
async def chat_justificacion(
    mensaje: str = Form(...),
    alumno_id: str = Form(...),
    padre_id: Optional[str] = Form(None),
    tipo_flujo: str = Form("JUSTIFICACION_MEDICA"),
):
    state = SharedState(
        alumno_id=alumno_id,
        incidencia_id=str(uuid.uuid4()),
        padre_id=padre_id,
        tipo_flujo=tipo_flujo,
        estado_actual="INICIO",
        fecha_actual=str(date.today()),
    )

    loop = asyncio.get_event_loop()
    try:
        resultado = await loop.run_in_executor(executor, _ejecutar_swarm, state, mensaje)
    except Exception as e:
        logger.exception("Error ejecutando swarm de agentes")
        raise HTTPException(
            status_code=502,
            detail=f"Error en el procesamiento del agente: {type(e).__name__} — {e}",
        )

    return ChatResponse(
        alumno_id=resultado.alumno_id,
        tipo_flujo=resultado.tipo_flujo,
        estado_actual=resultado.estado_actual,
        analisis_conductual=resultado.analisis_conductual,
        resultado_rag_reglamento=resultado.resultado_rag_reglamento,
        dictamen_final=resultado.dictamen_final,
        mcp_logs=resultado.mcp_logs,
    )


@router.post("/pre-falta")
async def solicitar_pre_falta(request: PreFaltaRequest):
    logger.info("Agente Evaluador: Consultando base de datos vectorial sobre historial y políticas...")
    logger.info("Agente Evaluador: Evaluación completada positivamente.")

    return {
        "status": "Permiso Pre-Aprobado por IA (Simulado)",
        "message": "El MCP de escritura se encargará de guardar este estado en la base de datos PostgreSQL cuando el servidor esté operativo.",
        "datos_procesados": request.model_dump(),
    }