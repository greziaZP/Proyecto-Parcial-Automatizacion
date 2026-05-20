"""
vector/seed_vectorial.py
========================
Seeder vectorial para Qdrant — Sistema de Asistencia Digital.

Sigue el mismo patrón que los seeders de db/seeds/:
  - Una función por colección (upsert idempotente)
  - Lee los datos ya existentes en PostgreSQL para construir el texto
  - Genera embeddings con sentence-transformers (all-MiniLM-L6-v2)
  - Carga los vectores en Qdrant

COLECCIONES (reglas de negocio):
  1. alertas_fuga        — Una por fuga detectada. Permite búsqueda semántica
                           sobre el texto de la observación del caso.
  2. notificaciones      — Una por notificación emitida (tutor, apoderado o
                           auxiliar). Distingue si el periodo es tutoría o no.
  3. excepciones_sin_resolver — Fugas en estado 'detectada' o 'notificada'
                           que requieren gestión manual desde el dashboard de
                           Supervisión.
  4. reportes_trimestrales — Un documento por (matrícula × período). Permite
                           al apoderado buscar su reporte en lenguaje natural.
  5. conducta_anual      — Resumen anual de conducta por estudiante. Se activa
                           al cierre del año para habilitar matrícula digital.

VARIABLES DE ENTORNO (.env raíz del proyecto):
  QDRANT_HOST           (default: localhost)
  QDRANT_PORT           (default: 6333)
  QDRANT_API_KEY        (opcional, para instancias con auth)
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
"""

import os
import sys
import uuid
import time
from pathlib import Path
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    UpdateStatus,
)
from sentence_transformers import SentenceTransformer

# ── Cargar .env desde raíz del proyecto ───────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# ── Dimensión del modelo de embeddings ────────────────────────────────────────
EMBED_DIM = 384          # all-MiniLM-L6-v2  →  384 dims

# ── Nombres de colecciones ────────────────────────────────────────────────────
COL_FUGAS        = "alertas_fuga"
COL_NOTIF        = "notificaciones"
COL_EXCEPCIONES  = "excepciones_sin_resolver"
COL_REPORTES     = "reportes_trimestrales"
COL_CONDUCTA     = "conducta_anual"
COL_REGLAMENTO   = "reglamento_institucional"

ALL_COLLECTIONS = [
    COL_FUGAS,
    COL_NOTIF,
    COL_EXCEPCIONES,
    COL_REPORTES,
    COL_CONDUCTA,
    COL_REGLAMENTO,
]

# ── Parámetros vectoriales para cada colección ────────────────────────────────
VECTOR_PARAMS = VectorParams(size=EMBED_DIM, distance=Distance.COSINE)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de conexión
# ─────────────────────────────────────────────────────────────────────────────

def _get_pg_conn() -> psycopg2.extensions.connection:
    """Abre conexión a PostgreSQL con las variables del .env."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
    )


def _get_qdrant() -> QdrantClient:
    """Retorna cliente Qdrant configurado con las variables del .env.

    NOTA: https=False es obligatorio para instancias locales (docker-compose).
    qdrant-client >=1.9 activa TLS automáticamente cuando se pasa api_key,
    pero el contenedor local no tiene certificado SSL.
    """
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
        api_key=api_key,
        https=False,   # forzar HTTP plano — sin TLS en entorno local
    )


def _ensure_collection(client: QdrantClient, name: str) -> None:
    """Crea la colección si no existe (idempotente)."""
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VECTOR_PARAMS,
        )
        print(f"   📦 Colección '{name}' creada.")
    else:
        print(f"   📦 Colección '{name}' ya existe — se hará upsert.")


def _upsert_batch(
    client: QdrantClient,
    collection: str,
    model: SentenceTransformer,
    texts: list[str],
    payloads: list[dict],
    ids: list[str],
) -> int:
    """
    Genera embeddings y hace upsert en Qdrant.
    Retorna número de puntos insertados/actualizados.
    """
    if not texts:
        return 0

    vectors = model.encode(texts, show_progress_bar=False).tolist()

    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, uid)),   # UUID v5 determinista
            vector=vec,
            payload={**pay, "_pg_uid": uid},               # siempre guardar el uid de PG
        )
        for uid, vec, pay in zip(ids, vectors, payloads)
    ]

    result = client.upsert(collection_name=collection, points=points)
    return len(points) if result.status == UpdateStatus.COMPLETED else 0


# ─────────────────────────────────────────────────────────────────────────────
# 1. Colección: alertas_fuga
# ─────────────────────────────────────────────────────────────────────────────

def seed_alertas_fuga(
    pg: psycopg2.extensions.connection,
    qd: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """
    Una fuga → un documento vectorial.

    Regla de negocio:
      El sistema detecta discrepancias entre 'ingreso registrado' y
      'permanencia en aula'. Cada fuga tiene una observación textual
      que debe ser buscable semánticamente por Supervisión.

    Texto del embedding:
      "<estado_fuga>: <observacion_caso>"
      Ejemplo: "detectada: Alumno salió sin autorización por puerta trasera."
    """
    _ensure_collection(qd, COL_FUGAS)
    print(f"🌱 Seeding {COL_FUGAS}...")

    cur = pg.cursor()
    cur.execute("""
        SELECT
            f.uid,
            f.estado_fuga,
            f.observacion_caso,
            f.fecha_hora_deteccion,
            f.fecha_hora_resolucion,
            ac.estudiante_uid,
            ac.horario_clase_uid,
            hc.es_hora_tutoria
        FROM fuga f
        JOIN asistencia_clase ac ON ac.uid = f.asistencia_clase_uid
        JOIN horario_clase hc    ON hc.uid = ac.horario_clase_uid
        ORDER BY f.fecha_hora_deteccion
    """)
    rows = cur.fetchall()
    cur.close()

    texts, payloads, ids = [], [], []
    for (fuga_uid, estado, observacion, det, res,
         est_uid, hc_uid, es_tutoria) in rows:

        texto = f"{estado}: {observacion or 'Sin observación registrada.'}"
        texts.append(texto)
        payloads.append({
            "estado_fuga": estado,
            "observacion": observacion,
            "estudiante_uid": str(est_uid),
            "horario_clase_uid": str(hc_uid),
            "es_hora_tutoria": bool(es_tutoria),
            "fecha_deteccion": str(det) if det else None,
            "fecha_resolucion": str(res) if res else None,
            "requiere_gestion_manual": estado in ("detectada", "notificada"),
        })
        ids.append(str(fuga_uid))

    n = _upsert_batch(qd, COL_FUGAS, model, texts, payloads, ids)
    print(f"✅ {n} alertas de fuga vectorizadas")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# 2. Colección: notificaciones
# ─────────────────────────────────────────────────────────────────────────────

def seed_notificaciones(
    pg: psycopg2.extensions.connection,
    qd: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """
    Una notificación por fuga, con destinatario y canal según la regla:

      • Si es hora de tutoría  → apoderado (App/SMS)
      • Si NO es hora tutoría  → auxiliar (alerta para localizar al estudiante)
      • Siempre               → tutor del salón (App/SMS)

    Genera 2 documentos por fuga (uno al tutor + uno al destinatario secundario).

    Regla de negocio:
      El sistema emite alertas automáticas diferenciando el periodo (tutoría vs
      clase normal) para notificar al actor correcto.
    """
    _ensure_collection(qd, COL_NOTIF)
    print(f"🌱 Seeding {COL_NOTIF}...")

    cur = pg.cursor()
    cur.execute("""
        SELECT
            f.uid,
            f.estado_fuga,
            f.observacion_caso,
            f.fecha_hora_deteccion,
            ac.estudiante_uid,
            hc.es_hora_tutoria,
            hc.docente_dictante_uid
        FROM fuga f
        JOIN asistencia_clase ac ON ac.uid = f.asistencia_clase_uid
        JOIN horario_clase hc    ON hc.uid = ac.horario_clase_uid
        ORDER BY f.fecha_hora_deteccion
    """)
    rows = cur.fetchall()
    cur.close()

    texts, payloads, ids = [], [], []
    for (fuga_uid, estado, observacion, det,
         est_uid, es_tutoria, docente_uid) in rows:

        # ── Notificación 1: al tutor del salón (siempre) ─────────────────────
        texto_tutor = (
            f"Alerta de fuga para tutor — Alumno UID {est_uid} — "
            f"Estado: {estado}. Periodo: {'tutoría' if es_tutoria else 'clase normal'}. "
            f"Motivo: {observacion or 'Sin detalle.'}"
        )
        texts.append(texto_tutor)
        payloads.append({
            "tipo_notificacion": "alerta_tutor",
            "destinatario_rol": "docente",
            "destinatario_uid": str(docente_uid) if docente_uid else None,
            "canal": "App/SMS",
            "estudiante_uid": str(est_uid),
            "es_hora_tutoria": bool(es_tutoria),
            "estado_fuga": estado,
            "fecha_deteccion": str(det) if det else None,
            "fuga_uid": str(fuga_uid),
        })
        ids.append(f"{fuga_uid}__tutor")

        # ── Notificación 2: destinatario secundario ───────────────────────────
        if es_tutoria:
            # → Notificar al apoderado
            texto_sec = (
                f"Notificación a apoderado — Fuga detectada durante hora de tutoría. "
                f"Alumno UID {est_uid}. {observacion or ''}"
            )
            tipo_notif = "alerta_apoderado"
            dest_rol   = "padre_familia"
            canal      = "App/SMS"
        else:
            # → Alerta al auxiliar para localizar al estudiante
            texto_sec = (
                f"Alerta a auxiliar — Alumno UID {est_uid} no localizado en aula. "
                f"Fuga en clase normal. {observacion or ''} — Estado: {estado}."
            )
            tipo_notif = "alerta_auxiliar"
            dest_rol   = "auxiliar"
            canal      = "App"

        texts.append(texto_sec)
        payloads.append({
            "tipo_notificacion": tipo_notif,
            "destinatario_rol": dest_rol,
            "destinatario_uid": None,   # se resuelve en runtime por el sistema
            "canal": canal,
            "estudiante_uid": str(est_uid),
            "es_hora_tutoria": bool(es_tutoria),
            "estado_fuga": estado,
            "fecha_deteccion": str(det) if det else None,
            "fuga_uid": str(fuga_uid),
        })
        ids.append(f"{fuga_uid}__secundario")

    n = _upsert_batch(qd, COL_NOTIF, model, texts, payloads, ids)
    print(f"✅ {n} notificaciones vectorizadas")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# 3. Colección: excepciones_sin_resolver
# ─────────────────────────────────────────────────────────────────────────────

def seed_excepciones_sin_resolver(
    pg: psycopg2.extensions.connection,
    qd: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """
    Fugas en estado 'detectada' o 'notificada' (no resueltas).

    Regla de negocio:
      El área de Registro Técnico (Supervisión) monitorea el dashboard en
      tiempo real. Cada alerta sin resolver debe ser gestionable manualmente
      (corrección o justificación). Este seeder vectoriza esas excepciones
      para que el dashboard pueda hacer búsqueda semántica.
    """
    _ensure_collection(qd, COL_EXCEPCIONES)
    print(f"🌱 Seeding {COL_EXCEPCIONES}...")

    cur = pg.cursor()
    cur.execute("""
        SELECT
            f.uid,
            f.estado_fuga,
            f.observacion_caso,
            f.fecha_hora_deteccion,
            f.auxiliar_detector_uid,
            f.auxiliar_registrador_uid,
            ac.estudiante_uid,
            ac.fecha_asistencia
        FROM fuga f
        JOIN asistencia_clase ac ON ac.uid = f.asistencia_clase_uid
        WHERE f.estado_fuga IN ('detectada', 'notificada')
        ORDER BY f.fecha_hora_deteccion DESC
    """)
    rows = cur.fetchall()
    cur.close()

    texts, payloads, ids = [], [], []
    for (fuga_uid, estado, observacion, det,
         aux_det, aux_reg, est_uid, fecha_asis) in rows:

        texto = (
            f"Excepción sin resolver — Estado: {estado}. "
            f"Alumno UID {est_uid}. Fecha: {fecha_asis}. "
            f"Observación: {observacion or 'No especificada.'}. "
            f"Requiere corrección o justificación manual por Supervisión."
        )
        texts.append(texto)
        payloads.append({
            "estado_fuga": estado,
            "estudiante_uid": str(est_uid),
            "fecha_asistencia": str(fecha_asis) if fecha_asis else None,
            "fecha_deteccion": str(det) if det else None,
            "auxiliar_detector_uid": str(aux_det) if aux_det else None,
            "auxiliar_registrador_uid": str(aux_reg) if aux_reg else None,
            "requiere_gestion_manual": True,
            "fuga_uid": str(fuga_uid),
        })
        ids.append(str(fuga_uid))

    n = _upsert_batch(qd, COL_EXCEPCIONES, model, texts, payloads, ids)
    print(f"✅ {n} excepciones sin resolver vectorizadas")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# 4. Colección: reportes_trimestrales
# ─────────────────────────────────────────────────────────────────────────────

def seed_reportes_trimestrales(
    pg: psycopg2.extensions.connection,
    qd: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """
    Un documento vectorial por (matrícula × período trimestral).

    Regla de negocio:
      Al fin de trimestre el sistema genera y envía el reporte digital al
      padre/apoderado (vía PDF/App). El apoderado debe poder acceder y buscar
      los detalles en tiempo real desde la aplicación usando lenguaje natural.

    Texto del embedding:
      Resumen textual del reporte: tardanzas, inasistencias, fugas, calificación.
    """
    _ensure_collection(qd, COL_REPORTES)
    print(f"🌱 Seeding {COL_REPORTES}...")

    cur = pg.cursor()
    cur.execute("""
        SELECT
            na.uid,
            na.matricula_uid,
            na.periodo_uid,
            na.total_tardanzas,
            na.total_inasistencias,
            na.total_fugas,
            na.calificacion_valor,
            na.promedio_academico,
            na.estado_reporte,
            pt.numero_trimestre,
            m.estudiante_uid,
            e.nombres  AS est_nombres,
            e.apellidos AS est_apellidos
        FROM nota_actitudinal na
        JOIN matricula m         ON m.uid = na.matricula_uid
        JOIN periodo_trimestral pt ON pt.uid = na.periodo_uid
        JOIN estudiante e        ON e.uid = m.estudiante_uid
        ORDER BY pt.numero_trimestre, m.estudiante_uid
    """)
    rows = cur.fetchall()
    cur.close()

    TRIM_NOMBRE = {1: "Primer", 2: "Segundo", 3: "Tercer"}

    texts, payloads, ids = [], [], []
    for (na_uid, mat_uid, per_uid, tardanzas, inasis, fugas,
         calif, promed, estado, num_trim, est_uid,
         nombres, apellidos) in rows:

        trim_str  = TRIM_NOMBRE.get(num_trim, f"{num_trim}°")
        calif_str = f"{float(calif):.2f}" if calif is not None else "N/D"
        prom_str  = f"{float(promed):.2f}" if promed is not None else "N/D"

        texto = (
            f"Reporte {trim_str} Trimestre — Alumno: {nombres} {apellidos}. "
            f"Tardanzas: {tardanzas}, Inasistencias: {inasis}, Fugas: {fugas}. "
            f"Calificación actitudinal: {calif_str}/20. "
            f"Promedio académico: {prom_str}. "
            f"Estado del reporte: {estado}."
        )
        texts.append(texto)
        payloads.append({
            "nota_actitudinal_uid": str(na_uid),
            "matricula_uid": str(mat_uid),
            "periodo_uid": str(per_uid),
            "numero_trimestre": num_trim,
            "total_tardanzas": tardanzas,
            "total_inasistencias": inasis,
            "total_fugas": fugas,
            "calificacion_valor": float(calif) if calif is not None else None,
            "promedio_academico": float(promed) if promed is not None else None,
            "estado_reporte": estado,
            "estudiante_uid": str(est_uid),
            "disponible_para_apoderado": estado == "publicado",
        })
        ids.append(str(na_uid))

    n = _upsert_batch(qd, COL_REPORTES, model, texts, payloads, ids)
    print(f"✅ {n} reportes trimestrales vectorizados")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# 5. Colección: conducta_anual
# ─────────────────────────────────────────────────────────────────────────────

def seed_conducta_anual(
    pg: psycopg2.extensions.connection,
    qd: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """
    Un documento vectorial por estudiante con su resumen anual de conducta.

    Regla de negocio:
      Al fin de año el sistema cierra la nota actitudinal anual y habilita el
      proceso de matrícula digital. Este documento consolida las métricas de
      conducta de los 3 trimestres para que el área académica pueda consultar
      el historial en lenguaje natural.

    Texto del embedding:
      Consolidado: nombre, totales anuales, promedio de calificación.
    """
    _ensure_collection(qd, COL_CONDUCTA)
    print(f"🌱 Seeding {COL_CONDUCTA}...")

    cur = pg.cursor()
    cur.execute("""
        SELECT
            m.uid             AS mat_uid,
            m.estudiante_uid,
            e.nombres,
            e.apellidos,
            SUM(na.total_tardanzas)     AS tard_anual,
            SUM(na.total_inasistencias) AS inas_anual,
            SUM(na.total_fugas)         AS fugas_anual,
            AVG(na.calificacion_valor)  AS calif_prom,
            AVG(na.promedio_academico)  AS acad_prom,
            COUNT(na.uid)               AS periodos_registrados
        FROM matricula m
        JOIN estudiante e      ON e.uid = m.estudiante_uid
        JOIN nota_actitudinal na ON na.matricula_uid = m.uid
        JOIN seccion s         ON s.uid = m.seccion_uid
        JOIN ano_escolar a     ON a.uid = s.ano_escolar_uid
        WHERE a.activo = TRUE
          AND m.estado_matricula = 'activa'
        GROUP BY m.uid, m.estudiante_uid, e.nombres, e.apellidos
        ORDER BY e.apellidos, e.nombres
    """)
    rows = cur.fetchall()
    cur.close()

    texts, payloads, ids = [], [], []
    for (mat_uid, est_uid, nombres, apellidos,
         tard, inas, fugas, calif_prom,
         acad_prom, periodos) in rows:

        calif_str = f"{float(calif_prom):.2f}" if calif_prom is not None else "N/D"
        acad_str  = f"{float(acad_prom):.2f}"  if acad_prom  is not None else "N/D"

        texto = (
            f"Conducta anual — Alumno: {nombres} {apellidos}. "
            f"Tardanzas acumuladas: {tard}, Inasistencias: {inas}, Fugas: {fugas}. "
            f"Calificación actitudinal promedio: {calif_str}/20. "
            f"Promedio académico anual: {acad_str}. "
            f"Períodos evaluados: {periodos} de 3. "
            f"Proceso de matrícula digital: "
            f"{'habilitado' if int(periodos or 0) == 3 else 'pendiente de cierre'}."
        )
        texts.append(texto)
        payloads.append({
            "matricula_uid": str(mat_uid),
            "estudiante_uid": str(est_uid),
            "nombres": nombres,
            "apellidos": apellidos,
            "tardanzas_anual": int(tard or 0),
            "inasistencias_anual": int(inas or 0),
            "fugas_anual": int(fugas or 0),
            "calificacion_promedio": float(calif_prom) if calif_prom else None,
            "promedio_academico_anual": float(acad_prom) if acad_prom else None,
            "periodos_registrados": int(periodos or 0),
            "matricula_digital_habilitada": int(periodos or 0) == 3,
            "generado_en": datetime.utcnow().isoformat(),
        })
        ids.append(str(mat_uid))

    n = _upsert_batch(qd, COL_CONDUCTA, model, texts, payloads, ids)
    print(f"✅ {n} resúmenes de conducta anual vectorizados")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# 6. Colección: reglamento_institucional  (datos estáticos — sin PG)
# ─────────────────────────────────────────────────────────────────────────────

def seed_reglamento_institucional(
    qd: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """
    Siembra las normas de justificación de inasistencias del reglamento
    institucional como documentos vectoriales estáticos (no dependen de PG).

    Regla de negocio:
      El EvaluadorAgent usa la herramienta `consultar_reglamento` para hacer
      búsqueda RAG sobre esta colección y decidir si una justificación de
      inasistencia es válida según la normativa vigente del colegio.

    Cada documento cubre un artículo específico del reglamento. El texto
    completo se embebe para habilitar búsqueda semántica por situación.
    """
    _ensure_collection(qd, COL_REGLAMENTO)
    print(f"🌱 Seeding {COL_REGLAMENTO}...")

    # ── Artículos del reglamento (datos estáticos) ────────────────────────────
    articulos = [
        {
            "id": "reglamento_art01",
            "articulo": "Art. 1",
            "categoria": "justificaciones",
            "texto": (
                "Art. 1 – Justificaciones válidas de inasistencia. "
                "Se consideran causas justificadas de inasistencia: la presentación de "
                "certificado médico emitido por un profesional de salud colegiado, "
                "la ocurrencia de una emergencia familiar debidamente documentada "
                "(hospitalización, fallecimiento de familiar directo), y el viaje oficial "
                "o representación institucional autorizada por la Dirección del plantel. "
                "Ninguna otra causa será aceptada salvo resolución expresa de la Dirección."
            ),
        },
        {
            "id": "reglamento_art02",
            "articulo": "Art. 2",
            "categoria": "justificaciones",
            "texto": (
                "Art. 2 – Plazo de presentación de la justificación. "
                "El apoderado o el propio estudiante (si es mayor de edad) dispone de "
                "un plazo máximo de 48 horas hábiles contadas desde el primer día de "
                "la falta para presentar la documentación justificatoria. "
                "Las justificaciones presentadas fuera de este plazo no serán admitidas "
                "y la inasistencia quedará registrada como injustificada de manera definitiva. "
                "En casos de hospitalización prolongada el plazo se extiende hasta 24 horas "
                "después del alta médica."
            ),
        },
        {
            "id": "reglamento_art03",
            "articulo": "Art. 3",
            "categoria": "justificaciones",
            "texto": (
                "Art. 3 – Límite de inasistencias injustificadas y sanción académica. "
                "El estudiante que acumule inasistencias injustificadas superiores al 30 % "
                "del total de sesiones programadas en cualquier área curricular durante "
                "un período trimestral será calificado con nota desaprobatoria (cero) "
                "en dicha área para ese período. "
                "Si las inasistencias injustificadas superan el 30 % en el año lectivo completo, "
                "el estudiante pierde el derecho a rendir exámenes de recuperación y "
                "deberá repetir el grado."
            ),
        },
        {
            "id": "reglamento_art04",
            "articulo": "Art. 4",
            "categoria": "justificaciones",
            "texto": (
                "Art. 4 – Modalidad de presentación de la justificación. "
                "El apoderado debe presentar la documentación justificatoria de forma "
                "presencial en la Secretaría del plantel o mediante la plataforma digital "
                "oficial registrada por la institución. "
                "No se aceptarán justificaciones enviadas por correo electrónico no "
                "institucional, mensajería instantánea ni redes sociales. "
                "La constancia de recepción emitida por la plataforma o por Secretaría "
                "es el único comprobante válido de presentación dentro del plazo."
            ),
        },
        {
            "id": "reglamento_art05",
            "articulo": "Art. 5",
            "categoria": "justificaciones",
            "texto": (
                "Art. 5 – Casos especiales: competencias y representación oficial. "
                "Los estudiantes convocados para representar al colegio en competencias "
                "deportivas, académicas, culturales o artísticas quedan exentos de las "
                "consecuencias académicas por inasistencia durante los días del evento. "
                "La exención debe ser autorizada previamente por la Dirección mediante "
                "memorándum interno y comunicada a los docentes de cada área. "
                "El estudiante deberá ponerse al día con los contenidos en un plazo "
                "no mayor a cinco días hábiles tras su reintegro."
            ),
        },
        {
            "id": "reglamento_art06",
            "articulo": "Art. 6",
            "categoria": "justificaciones",
            "texto": (
                "Art. 6 – Proceso de apelación de inasistencias injustificadas. "
                "El apoderado que considere incorrecta la calificación de una inasistencia "
                "como injustificada puede presentar una apelación formal ante la Dirección "
                "académica dentro de los cinco días hábiles siguientes a la notificación. "
                "La Dirección resolverá la apelación en un plazo máximo de diez días hábiles, "
                "previa evaluación de la documentación adicional aportada. "
                "La decisión de la Dirección es inapelable en sede institucional, "
                "sin perjuicio de los recursos ante la autoridad educativa superior."
            ),
        },
        {
            "id": "reglamento_art07",
            "articulo": "Art. 7",
            "categoria": "justificaciones",
            "texto": (
                "Art. 7 – Inasistencias por enfermedad crónica o tratamiento médico continuo. "
                "Los estudiantes con diagnóstico de enfermedad crónica o que sigan un "
                "tratamiento médico de larga duración pueden acogerse al régimen de "
                "asistencia especial, previa presentación del informe médico al inicio "
                "del año escolar o en el momento del diagnóstico. "
                "Bajo este régimen, las inasistencias vinculadas al tratamiento no "
                "computarán para el límite del 30 % establecido en el Art. 3, "
                "siempre que el apoderado notifique cada ausencia dentro de las 24 horas."
            ),
        },
        {
            "id": "reglamento_art08",
            "articulo": "Art. 8",
            "categoria": "justificaciones",
            "texto": (
                "Art. 8 – Registro y seguimiento de asistencia. "
                "El registro de asistencia es responsabilidad del docente a cargo de "
                "cada sesión de aprendizaje y debe ser ingresado al sistema dentro de "
                "los primeros diez minutos de iniciada la clase. "
                "Cualquier discrepancia entre el registro del docente y el sistema "
                "biométrico de control de ingreso será resuelta por el área de "
                "Supervisión, que emitirá la versión definitiva en un plazo de 24 horas. "
                "El historial de asistencia es público para el apoderado a través de la "
                "plataforma institucional."
            ),
        },
        {
            "id": "reglamento_art09",
            "articulo": "Art. 9",
            "categoria": "justificaciones",
            "texto": (
                "Art. 9 – Tardanzas reiteradas como equivalente a inasistencia. "
                "Tres tardanzas injustificadas en un mismo período trimestral equivalen "
                "a una inasistencia injustificada a efectos del cómputo del Art. 3. "
                "Se entiende por tardanza el ingreso al aula con más de diez minutos "
                "de retraso respecto al horario oficial de inicio de la sesión. "
                "El docente debe registrar la tardanza en el sistema con la misma "
                "inmediatez que la inasistencia, indicando la hora real de ingreso."
            ),
        },
        {
            "id": "reglamento_art10",
            "articulo": "Art. 10",
            "categoria": "justificaciones",
            "texto": (
                "Art. 10 – Notificación al apoderado y comunicación oportuna. "
                "El sistema enviará una notificación automática al apoderado registrado "
                "cada vez que el estudiante acumule una inasistencia injustificada, "
                "y una alerta de riesgo académico cuando supere el 20 % del límite "
                "establecido en el Art. 3. "
                "Es responsabilidad del apoderado mantener actualizados sus datos de "
                "contacto en la plataforma institucional. "
                "La no recepción de la notificación por datos desactualizados no exime "
                "al estudiante de las consecuencias académicas descritas en el reglamento."
            ),
        },
    ]

    texts    = [a["texto"]    for a in articulos]
    payloads = [
        {
            "articulo": a["articulo"],
            "categoria": a["categoria"],
            "texto": a["texto"]
        }
        for a in articulos
    ]
    ids      = [a["id"]       for a in articulos]

    n = _upsert_batch(qd, COL_REGLAMENTO, model, texts, payloads, ids)
    print(f"✅ {n} artículos del reglamento institucional vectorizados")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────────────────────────────────────

def _paso(nombre: str, fn, *args) -> int:
    """Ejecuta una función de seeding midiendo tiempo y capturando errores."""
    print(f"\n{'─'*55}")
    t0 = time.time()
    try:
        result = fn(*args)
        elapsed = time.time() - t0
        print(f"   ⏱  {elapsed:.1f}s")
        return result
    except Exception as e:
        print(f"❌ Error en '{nombre}': {e}")
        raise


def run_all() -> None:
    """Ejecuta todos los seeders vectoriales en orden."""
    inicio = time.time()
    print("🚀 Iniciando seeding vectorial — Sistema de Asistencia Digital")
    print("=" * 55)
    print(f"   Qdrant:    {os.getenv('QDRANT_HOST','localhost')}:{os.getenv('QDRANT_PORT','6333')}")
    print(f"   Postgres:  {os.getenv('POSTGRES_HOST','localhost')}:{os.getenv('POSTGRES_PORT','5432')}")
    print(f"   Modelo:    all-MiniLM-L6-v2  ({EMBED_DIM}d, cosine)")
    print("=" * 55)

    print("\n🔌 Conectando a PostgreSQL...")
    pg = _get_pg_conn()

    print("🔌 Conectando a Qdrant...")
    qd = _get_qdrant()

    print("🧠 Cargando modelo de embeddings (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    try:
        # ── Nivel A: Incidencias detectadas ───────────────────────────────────
        print("\n📦 NIVEL A — Alertas de fuga (detección de discrepancias)")
        _paso("alertas_fuga", seed_alertas_fuga, pg, qd, model)

        # ── Nivel B: Notificaciones generadas ─────────────────────────────────
        print("\n📦 NIVEL B — Notificaciones (protocolo de alerta)")
        _paso("notificaciones", seed_notificaciones, pg, qd, model)

        # ── Nivel C: Excepciones sin resolver (Supervisión) ───────────────────
        print("\n📦 NIVEL C — Excepciones sin resolver (dashboard Supervisión)")
        _paso("excepciones_sin_resolver", seed_excepciones_sin_resolver, pg, qd, model)

        # ── Nivel D: Reportes trimestrales (apoderado) ────────────────────────
        print("\n📦 NIVEL D — Reportes trimestrales (acceso apoderado)")
        _paso("reportes_trimestrales", seed_reportes_trimestrales, pg, qd, model)

        # ── Nivel E: Conducta anual (cierre de año) ───────────────────────────
        print("\n📦 NIVEL E — Conducta anual (cierre de año / matrícula digital)")
        _paso("conducta_anual", seed_conducta_anual, pg, qd, model)

        # ── Nivel F: Reglamento institucional (RAG del EvaluadorAgent) ────────
        print("\n📦 NIVEL F — Reglamento institucional (RAG justificaciones)")
        _paso("reglamento_institucional", seed_reglamento_institucional, qd, model)

        total_s = time.time() - inicio
        print(f"\n{'='*55}")
        print(f"🎉 ¡Seeding vectorial completo en {total_s:.1f}s!")
        print(f"{'='*55}")
        print("\n📊 Colecciones creadas/actualizadas en Qdrant:")
        for col in ALL_COLLECTIONS:
            info = qd.get_collection(col)
            print(f"   • {col:<30} → {info.points_count} puntos")

    except Exception as e:
        print(f"\n❌ Seeding vectorial interrumpido: {e}")
        sys.exit(1)
    finally:
        pg.close()


if __name__ == "__main__":
    run_all()
    sys.exit(0)
