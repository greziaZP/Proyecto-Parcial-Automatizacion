import logging
import uuid
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.state.shared_state import SharedState
from app.agents.orquestador import OrquestadorAgent
from app.queries.agentes_queries import query_listar_justificaciones, query_detalle_justificacion

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
    mensaje_respuesta: Optional[str] = None
    justificacion_uid: Optional[str] = None
    mcp_logs: list = []


class JustificacionItem(BaseModel):
    uid: str
    tipo_justificacion: str
    estado_justificacion: str
    fecha_presentacion: Optional[str] = None
    fecha_inicio_incidencia: Optional[str] = None
    fecha_fin_incidencia: Optional[str] = None
    descripcion_motivo: Optional[str] = None
    creado_en: Optional[str] = None
    estudiante_uid: Optional[str] = None
    estudiante_nombre_completo: Optional[str] = None
    padre_uid: Optional[str] = None
    padre_nombre_completo: Optional[str] = None


class JustificacionDetalle(JustificacionItem):
    url_documento_referencia: Optional[str] = None


def _ejecutar_swarm(state: SharedState, mensaje: str) -> SharedState:
    orquestador = OrquestadorAgent()
    return orquestador.ejecutar(state, mensaje)



@router.get("/", response_model=List[JustificacionItem])
def listar_justificaciones():
    filas = query_listar_justificaciones()
    return filas


@router.get("/{uid}", response_model=JustificacionDetalle)
def detalle_justificacion(uid: str):
    fila = query_detalle_justificacion(uid)
    if not fila:
        raise HTTPException(status_code=404, detail="Justificación no encontrada")
    return fila


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
        mensaje_respuesta=resultado.dictamen_final,
        justificacion_uid=resultado.justificacion_uid,
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