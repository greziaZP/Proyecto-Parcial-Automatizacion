"""
routers/dashboard.py — Endpoints para el Dashboard del docente.
===============================================================
Reemplaza los mocks con queries reales a PostgreSQL.

Endpoints:
  GET /dashboard/horario-hoy     → clases del día actual
  GET /dashboard/proxima-clase   → siguiente clase más cercana en el tiempo
  GET /dashboard/stats           → estadísticas de asistencia del día
  GET /dashboard/incidencias/{aula_id}  → (legacy, mantenido por compatibilidad)
  GET /dashboard/citaciones             → (legacy, mock)
"""
from datetime import date, datetime
from typing import List, Dict, Any

from fastapi import APIRouter

from db import db_cursor

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Mapeo Python weekday → ENUM dia_semana de la BD
_DIAS = {0: "lunes", 1: "martes", 2: "miercoles",
         3: "jueves", 4: "viernes"}


def _dia_hoy() -> str:
    return _DIAS.get(date.today().weekday(), "lunes")


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/horario-hoy
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/horario-hoy", summary="Todas las clases programadas para hoy")
def horario_hoy():
    """
    Retorna todos los bloques horarios del día actual del año escolar activo.
    Usado por dashboard.py (UI) para poblar la lista 'Today's Classes'.
    """
    dia = _dia_hoy()
    with db_cursor() as cur:
        cur.execute("""
            SELECT
                h.uid,
                h.hora_inicio::text,
                h.hora_fin::text,
                h.es_hora_tutoria,
                c.nombre   AS curso_nombre,
                c.codigo   AS curso_codigo,
                d.nombres || ' ' || d.apellidos AS docente_nombre,
                d.uid      AS docente_uid,
                s.grado_academico,
                s.codigo_seccion,
                (s.grado_academico || ' ' || s.codigo_seccion) AS seccion_label,
                s.uid      AS seccion_uid
            FROM horario_clase h
            JOIN curso   c ON c.uid = h.curso_uid
            JOIN docente d ON d.uid = h.docente_dictante_uid
            JOIN seccion s ON s.uid = h.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE h.dia_semana = %s
              AND a.activo = TRUE
            ORDER BY h.hora_inicio, s.grado_academico, s.codigo_seccion
        """, (dia,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/proxima-clase
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/proxima-clase", summary="Próxima clase más cercana al momento actual")
def proxima_clase():
    """
    Retorna el horario más próximo a la hora actual del día.
    Si ya pasaron todas las clases, retorna la primera del día.
    Usado para el CTA del dashboard.
    """
    dia  = _dia_hoy()
    hora_actual = datetime.now().strftime("%H:%M")

    with db_cursor() as cur:
        # Primero intenta la próxima clase que aún no empezó
        cur.execute("""
            SELECT
                h.uid,
                h.hora_inicio::text,
                h.hora_fin::text,
                c.nombre   AS curso_nombre,
                d.nombres || ' ' || d.apellidos AS docente_nombre,
                d.uid      AS docente_uid,
                (s.grado_academico || ' ' || s.codigo_seccion) AS seccion_label,
                s.uid      AS seccion_uid,
                (
                    SELECT COUNT(*) FROM matricula m2
                    WHERE m2.seccion_uid = s.uid AND m2.estado_matricula = 'activa'
                ) AS total_alumnos
            FROM horario_clase h
            JOIN curso   c ON c.uid = h.curso_uid
            JOIN docente d ON d.uid = h.docente_dictante_uid
            JOIN seccion s ON s.uid = h.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE h.dia_semana  = %s
              AND a.activo      = TRUE
              AND h.hora_inicio >= %s
            ORDER BY h.hora_inicio
            LIMIT 1
        """, (dia, hora_actual))
        row = cur.fetchone()

        # Si no hay próxima, retorna la primera del día
        if not row:
            cur.execute("""
                SELECT
                    h.uid,
                    h.hora_inicio::text,
                    h.hora_fin::text,
                    c.nombre   AS curso_nombre,
                    d.nombres || ' ' || d.apellidos AS docente_nombre,
                    d.uid      AS docente_uid,
                    (s.grado_academico || ' ' || s.codigo_seccion) AS seccion_label,
                    s.uid      AS seccion_uid,
                    (
                        SELECT COUNT(*) FROM matricula m2
                        WHERE m2.seccion_uid = s.uid AND m2.estado_matricula = 'activa'
                    ) AS total_alumnos
                FROM horario_clase h
                JOIN curso   c ON c.uid = h.curso_uid
                JOIN docente d ON d.uid = h.docente_dictante_uid
                JOIN seccion s ON s.uid = h.seccion_uid
                JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
                WHERE h.dia_semana = %s
                  AND a.activo     = TRUE
                ORDER BY h.hora_inicio
                LIMIT 1
            """, (dia,))
            row = cur.fetchone()

    return dict(row) if row else {}


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/stats
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/stats", summary="Estadísticas de asistencia del día actual")
def stats_hoy():
    """
    Conteo de registros de ingreso del día (tabla registro_ingreso).
    Usado por el dashboard para mostrar KPIs rápidos.
    """
    hoy = date.today()
    with db_cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*)                                         AS total,
                COUNT(*) FILTER (WHERE estado_ingreso = 'a_tiempo')  AS a_tiempo,
                COUNT(*) FILTER (WHERE estado_ingreso = 'tardanza')  AS tardanza,
                COUNT(*) FILTER (WHERE estado_ingreso = 'ausente')   AS ausente
            FROM registro_ingreso
            WHERE fecha_ingreso = %s
        """, (hoy,))
        row = cur.fetchone()
    return dict(row) if row else {
        "total": 0, "a_tiempo": 0, "tardanza": 0, "ausente": 0
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/incidencias/{aula_id}  — legacy, ahora con datos reales
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/incidencias/{seccion_uid}", summary="Asistencia del día para una sección")
def listar_incidencias(seccion_uid: str) -> List[Dict[str, Any]]:
    """
    Retorna el estado de asistencia de hoy para todos los alumnos
    de la sección dada (registro_ingreso, no por clase).
    """
    hoy = date.today()
    with db_cursor() as cur:
        cur.execute("""
            SELECT
                e.dni_estudiante                        AS alumno_id,
                e.nombres || ' ' || e.apellidos         AS nombre,
                COALESCE(ri.estado_ingreso::text, 'sin_registro') AS estado,
                TO_CHAR(ri.hora_llegada, 'HH12:MI AM')  AS hora_marcacion
            FROM matricula  m
            JOIN estudiante e  ON e.uid = m.estudiante_uid
            LEFT JOIN registro_ingreso ri
                   ON ri.matricula_uid  = m.uid
                  AND ri.fecha_ingreso  = %s
            WHERE m.seccion_uid      = %s
              AND m.estado_matricula = 'activa'
            ORDER BY e.apellidos, e.nombres
        """, (hoy, seccion_uid))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# GET /dashboard/citaciones  — legacy mock (sin cambios)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/citaciones", summary="Citaciones agendadas por la IA (mock)")
async def listar_citaciones() -> List[Dict[str, Any]]:
    """
    Mock temporal. A futuro: leer citas generadas por el agente desde BD.
    """
    return [
        {
            "citacion_id": "C-1001",
            "alumno_id": "A192",
            "motivo": "Reincidencia de faltas injustificadas (3 veces en el último mes)",
            "departamento": "Psicopedagogía",
            "fecha_reunion": "2026-05-20T10:00:00Z",
            "agendado_por": "IA Autónoma",
        },
        {
            "citacion_id": "C-1002",
            "alumno_id": "A043",
            "motivo": "Patrón de llegadas tardías detectado",
            "departamento": "Dirección Académica",
            "fecha_reunion": "2026-05-21T08:30:00Z",
            "agendado_por": "IA Autónoma",
        },
    ]
