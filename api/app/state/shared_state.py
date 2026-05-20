from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class SharedState(BaseModel):
    """
    Memoria Compartida (Shared State) que viaja y muta a través 
    de los distintos agentes del Swarm.
    """
    # Identificadores basicos
    alumno_id: str
    incidencia_id: Optional[str] = None
    padre_id: Optional[str] = None
    docente_id: Optional[str] = None
    
    # Estado del flujo
    tipo_flujo: str
    estado_actual: str
    fecha_actual: Optional[str] = None
    
    # Diagnósticos o textos acumulados de cada agente
    analisis_conductual: Optional[str] = None
    resultado_rag_reglamento: Optional[str] = None
    dictamen_final: Optional[str] = None
    justificacion_uid: Optional[str] = None
    
    # Registro de herramientas MCP ejecutadas
    mcp_logs: List[Dict[str, Any]] = Field(default_factory=list)

