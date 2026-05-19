from app.mcp.schemas import (
    BuscarHistorialInput,
    BuscarHistorialOutput,
    RegistrarCitacionInput,
    RegistrarCitacionOutput
)

def buscar_historial(input_data: BuscarHistorialInput) -> BuscarHistorialOutput:
    """
    Busca el historial completo de asistencia y comportamiento de un estudiante en PostgreSQL.
    
    Esencial para que el Agente Analista pueda evaluar el patrón conductual y
    determinar si una falta es recurrente o un incidente aislado.
    """
    raise NotImplementedError("Database connection not yet implemented")

def registrar_citacion(input_data: RegistrarCitacionInput) -> RegistrarCitacionOutput:
    """
    Registra de manera formal una nueva citación presencial entre el departamento 
    (ej. Psicopedagogía o Dirección) y los apoderados del estudiante en PostgreSQL.
    
    Invocar únicamente cuando el flujo agéntico determinó que la falta requiere
    intervención humana superior.
    """
    raise NotImplementedError("Database connection not yet implemented")
