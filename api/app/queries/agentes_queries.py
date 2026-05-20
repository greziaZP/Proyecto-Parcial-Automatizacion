import os
import uuid as _uuid
from datetime import date
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
from psycopg2.extensions import adapt
from typing import Dict, Any

register_uuid()

def _coerce_uuid(value):
    if value is None:
        return None
    if isinstance(value, _uuid.UUID):
        return str(value)
    return str(value)

# Función local para obtener conexión a PostgreSQL
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST") or os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT") or os.getenv("PG_PORT", "5432")),
        user=os.getenv("POSTGRES_USER") or os.getenv("PG_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD") or os.getenv("PG_PASSWORD", ""),
        dbname=os.getenv("POSTGRES_DB") or os.getenv("PG_DATABASE", "postgres")
    )

def query_historial_estudiante(estudiante_uid: str) -> Dict[str, Any]:
    """
    Trae las últimas 10 faltas/tardanzas desde asistencia_clase y 
    los acumulados desde nota_actitudinal cruzando por matricula.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Traer últimas 10 inasistencias/tardanzas
            cur.execute("""
                SELECT fecha_asistencia, estado_asistencia, observacion_docente
                FROM asistencia_clase
                WHERE estudiante_uid = %s 
                  AND estado_asistencia IN ('falta', 'tardanza')
                ORDER BY fecha_asistencia DESC
                LIMIT 10;
            """, (estudiante_uid,))
            faltas = cur.fetchall()

            # 2. Traer acumulados del periodo de notas
            cur.execute("""
                SELECT n.total_tardanzas, n.total_inasistencias, n.total_fugas, n.promedio_academico
                FROM nota_actitudinal n
                JOIN matricula m ON n.matricula_uid = m.uid
                WHERE m.estudiante_uid = %s
                ORDER BY n.calculado_en DESC
                LIMIT 1;
            """, (estudiante_uid,))
            acumulados = cur.fetchone()

        return {
            "ultimas_faltas_tardanzas": [dict(f) for f in faltas],
            "acumulados": dict(acumulados) if acumulados else {}
        }
    finally:
        conn.close()

_TIPO_JUSTIFICACION_MAP = {
    'JUSTIFICACION_MEDICA': 'medica',
    'JUSTIFICACION_FAMILIAR': 'familiar',
    'JUSTIFICACION_VIAJE': 'viaje',
    'JUSTIFICACION_OTRA': 'otra',
    'medica': 'medica',
    'familiar': 'familiar',
    'viaje': 'viaje',
    'otra': 'otra',
}

def _normalizar_tipo_justificacion(valor: str) -> str:
    return _TIPO_JUSTIFICACION_MAP.get(valor, 'otra')

def query_upsert_justificacion(datos_justificacion: dict) -> str:
    """
    Inserta una justificacion formal con los datos recibidos.
    Retorna el uid generado.
    """
    tipo = _normalizar_tipo_justificacion(
        datos_justificacion.get('tipo_justificacion', 'otra')
    )
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO justificacion (
                    asistencia_clase_uid,
                    tipo_justificacion,
                    estado_justificacion,
                    padre_solicitante_uid,
                    fecha_presentacion,
                    fecha_inicio_incidencia,
                    fecha_fin_incidencia,
                    descripcion_motivo
                ) VALUES (
                    %(asistencia_clase_uid)s,
                    %(tipo_justificacion)s::tipo_justificacion,
                    %(estado_justificacion)s::estado_justificacion,
                    %(padre_solicitante_uid)s,
                    %(fecha_presentacion)s,
                    %(fecha_inicio_incidencia)s,
                    %(fecha_fin_incidencia)s,
                    %(descripcion_motivo)s
                ) RETURNING uid;
            """, {
                'asistencia_clase_uid': _coerce_uuid(datos_justificacion.get('asistencia_clase_uid')),
                'tipo_justificacion': tipo,
                'estado_justificacion': datos_justificacion.get('estado_justificacion', 'pendiente'),
                'padre_solicitante_uid': _coerce_uuid(datos_justificacion.get('padre_solicitante_uid')),
                'fecha_presentacion': datos_justificacion.get('fecha_presentacion', date.today().isoformat()),
                'fecha_inicio_incidencia': datos_justificacion.get('fecha_inicio_incidencia'),
                'fecha_fin_incidencia': datos_justificacion.get('fecha_fin_incidencia'),
                'descripcion_motivo': datos_justificacion.get('descripcion_motivo'),
            })
            nuevo_uid = cur.fetchone()[0]
            conn.commit()
            return str(nuevo_uid)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def query_insert_citacion(datos_citacion: dict) -> str:
    """
    Inserta el registro de citación en PostgreSQL.
    Retorna el uid generado.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO citacion (
                    estudiante_uid,
                    padre_apoderado_uid,
                    docente_solicitante_uid,
                    motivo,
                    nivel_urgencia,
                    estado,
                    fecha_citacion
                ) VALUES (
                    %(estudiante_uid)s,
                    %(padre_apoderado_uid)s,
                    %(docente_solicitante_uid)s,
                    %(motivo)s,
                    %(nivel_urgencia)s,
                    %(estado)s,
                    %(fecha_citacion)s
                ) RETURNING uid;
            """, {
                'estudiante_uid': _coerce_uuid(datos_citacion.get('estudiante_uid')),
                'padre_apoderado_uid': _coerce_uuid(datos_citacion.get('padre_apoderado_uid')),
                'docente_solicitante_uid': _coerce_uuid(datos_citacion.get('docente_solicitante_uid')),
                'motivo': datos_citacion.get('motivo'),
                'nivel_urgencia': datos_citacion.get('nivel_urgencia', 'alta'),
                'estado': datos_citacion.get('estado', 'programada'),
                'fecha_citacion': datos_citacion.get('fecha_citacion')
            })
            nuevo_uid = cur.fetchone()[0]
            conn.commit()
            return str(nuevo_uid)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
