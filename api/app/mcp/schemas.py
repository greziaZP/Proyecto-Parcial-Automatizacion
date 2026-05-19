from pydantic import BaseModel
from typing import List, Dict, Any

class BuscarHistorialInput(BaseModel):
    alumno_id: str

class BuscarHistorialOutput(BaseModel):
    historial_asistencia: List[Dict[str, Any]]
    historial_conductual: List[Dict[str, Any]]

class ConsultarReglamentoInput(BaseModel):
    query: str

class ConsultarReglamentoOutput(BaseModel):
    articulos_relevantes: List[str]
    contexto_extraido: str

class RegistrarCitacionInput(BaseModel):
    alumno_id: str
    motivo: str
    departamento: str
    fecha_estimada: str

class RegistrarCitacionOutput(BaseModel):
    citacion_id: str
    status: str
