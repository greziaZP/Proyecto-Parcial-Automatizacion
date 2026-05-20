from app.mcp.schemas import (
    BuscarHistorialInput,
    BuscarHistorialOutput,
    RegistrarCitacionInput,
    RegistrarCitacionOutput,
    GestionarJustificacionInput,
    GestionarJustificacionOutput
)
from app.queries.agentes_queries import (
    query_historial_estudiante,
    query_upsert_justificacion,
    query_insert_citacion
)

def mcp_buscar_historial_estudiante(input_data: BuscarHistorialInput) -> BuscarHistorialOutput:
    """
    Busca el historial real de asistencia y comportamiento de un estudiante en PostgreSQL.
    """
    resultado = query_historial_estudiante(str(input_data.estudiante_uid))
    return BuscarHistorialOutput(
        ultimas_faltas_tardanzas=resultado["ultimas_faltas_tardanzas"],
        acumulados=resultado["acumulados"]
    )

def mcp_gestionar_justificacion(input_data: GestionarJustificacionInput) -> GestionarJustificacionOutput:
    """
    Inserta una justificación formal conectada a la base de datos real.
    """
    datos = input_data.model_dump(mode="json", exclude_unset=True)
    # Formateo explícito si es necesario, psycopg2 suele lidiar bien con types de python
    uid_generado = query_upsert_justificacion(datos)
    return GestionarJustificacionOutput(
        justificacion_uid=uid_generado,
        status="success"
    )


def mcp_registrar_citacion(input_data: RegistrarCitacionInput) -> RegistrarCitacionOutput:
    """
    Registra de manera formal una nueva citación presencial en PostgreSQL.
    """
    datos = input_data.model_dump(mode="json", exclude_unset=True)
    uid_generado = query_insert_citacion(datos)
    return RegistrarCitacionOutput(
        citacion_uid=uid_generado,
        status="success"
    )
