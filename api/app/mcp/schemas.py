from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import date, datetime

class BuscarHistorialInput(BaseModel):
    estudiante_uid: UUID

class BuscarHistorialOutput(BaseModel):
    ultimas_faltas_tardanzas: List[Dict[str, Any]]
    acumulados: Dict[str, Any]

class GestionarJustificacionInput(BaseModel):
    padre_solicitante_uid: UUID
    tipo_justificacion: str
    fecha_inicio_incidencia: date
    fecha_fin_incidencia: date
    descripcion_motivo: str
    asistencia_clase_uid: Optional[UUID] = None
    estado_justificacion: str = "pendiente"

class GestionarJustificacionOutput(BaseModel):
    justificacion_uid: UUID
    status: str

class ConsultarReglamentoInput(BaseModel):
    query: str

class ConsultarReglamentoOutput(BaseModel):
    articulos_relevantes: List[str]
    contexto_extraido: str

class RegistrarCitacionInput(BaseModel):
    estudiante_uid: UUID
    padre_apoderado_uid: UUID
    docente_solicitante_uid: UUID
    motivo: str
    nivel_urgencia: str = "alta"
    fecha_citacion: datetime

class RegistrarCitacionOutput(BaseModel):
    citacion_uid: UUID
    status: str
