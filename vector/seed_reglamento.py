"""
seed_reglamento.py — Seeder vectorial de reglas del Reglamento Interno
======================================================================
Inserta artículos del reglamento (Art. 10–14) como documentos vectoriales
en Qdrant para que los agentes LLM puedan hacer búsqueda semántica (RAG)
y aplicar las reglas correctas según el caso.

Cada artículo se guarda como un punto con:
  - vector:   embedding del texto completo (modelo all-MiniLM-L6-v2, 384d)
  - payload:  metadatos estructurados (artículo, categoría, reglas clave, etc.)

Uso:
    source .venv/bin/activate
    python seed_reglamento.py

Requisitos:
    - Qdrant corriendo en localhost:6333 (docker compose up -d)
    - Dependencias instaladas (qdrant-client, sentence-transformers, python-dotenv)
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# ── Cargar .env desde la raíz del proyecto ────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# ── Imports pesados (después del dotenv) ──────────────────────────────────────
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from sentence_transformers import SentenceTransformer


# =============================================================================
#  ARTÍCULOS DEL REGLAMENTO  (Art. 10 – 14)
# =============================================================================

ARTICULOS_REGLAMENTO = [
    # ── Art. 10: Inasistencias por salud ──────────────────────────────────────
    {
        "id": 10,
        "articulo": "Art. 10",
        "titulo": "Inasistencias por motivos de salud leves y graves",
        "categoria": "salud",
        "texto_completo": (
            "Art. 10 – Inasistencias por motivos de salud leves y graves. "
            "Las inasistencias por enfermedad de un (1) solo día pueden ser "
            "justificadas con una nota escrita y firmada por el apoderado a "
            "través de la plataforma. Sin embargo, si la inasistencia por "
            "salud se prolonga por dos (2) o más días consecutivos, es "
            "estrictamente obligatorio adjuntar un certificado médico, receta "
            "o constancia de atención firmada por un profesional de la salud "
            "colegiado. Sin este documento, los días adicionales se "
            "considerarán como faltas injustificadas."
        ),
        "reglas_clave": [
            "1 día de enfermedad → nota del apoderado basta",
            "2+ días consecutivos → certificado médico obligatorio",
            "Sin certificado médico en 2+ días → falta injustificada",
        ],
        "umbral_dias": 2,
        "documento_requerido_1_dia": "nota_apoderado",
        "documento_requerido_2_mas_dias": "certificado_medico",
    },

    # ── Art. 11: Fuerza mayor ─────────────────────────────────────────────────
    {
        "id": 11,
        "articulo": "Art. 11",
        "titulo": "Eventos de fuerza mayor, clima y transporte",
        "categoria": "fuerza_mayor",
        "texto_completo": (
            "Art. 11 – Eventos de fuerza mayor, clima y transporte. "
            "Se justificará la inasistencia o tardanza por eventos de fuerza "
            "mayor, tales como desastres naturales (lluvias torrenciales, "
            "inundaciones), bloqueos de vías o paros de transporte, siempre "
            "y cuando el evento sea de conocimiento público u oficializado "
            "por Defensa Civil. Si el evento afecta únicamente a la vivienda "
            "del estudiante (ej. aniego local, falla mecánica del vehículo "
            "particular), el apoderado debe adjuntar evidencia fotográfica o "
            "constancia policial en un plazo no mayor a 24 horas."
        ),
        "reglas_clave": [
            "Evento público (Defensa Civil) → justificación automática",
            "Evento privado (aniego local, falla vehículo) → evidencia fotográfica o constancia policial",
            "Plazo para evidencia privada: máximo 24 horas",
        ],
        "tipos_evento": ["desastre_natural", "bloqueo_vias", "paro_transporte", "aniego_local", "falla_vehicular"],
        "plazo_evidencia_horas": 24,
    },

    # ── Art. 12: Duelo familiar ───────────────────────────────────────────────
    {
        "id": 12,
        "articulo": "Art. 12",
        "titulo": "Licencia por duelo y calamidad doméstica",
        "categoria": "duelo",
        "texto_completo": (
            "Art. 12 – Licencia por duelo y calamidad doméstica. "
            "En caso de fallecimiento de un familiar directo (padres, "
            "hermanos, abuelos o tutores legales), el estudiante tiene "
            "derecho a una licencia con goce de justificación automática "
            "por tres (3) días hábiles consecutivos. Para familiares de "
            "segundo grado (tíos, primos), la justificación será de máximo "
            "un (1) día. El apoderado deberá regularizar el sustento "
            "presentando el acta de defunción correspondiente dentro de los "
            "cinco (5) días posteriores al retorno del alumno."
        ),
        "reglas_clave": [
            "Familiar directo (padres, hermanos, abuelos, tutores) → 3 días hábiles justificados",
            "Familiar segundo grado (tíos, primos) → 1 día justificado",
            "Acta de defunción → plazo de 5 días después del retorno",
        ],
        "dias_familiar_directo": 3,
        "dias_familiar_segundo_grado": 1,
        "familiares_directos": ["padres", "hermanos", "abuelos", "tutores_legales"],
        "familiares_segundo_grado": ["tios", "primos"],
        "plazo_acta_defuncion_dias": 5,
    },

    # ── Art. 13: Tardanzas acumuladas ─────────────────────────────────────────
    {
        "id": 13,
        "articulo": "Art. 13",
        "titulo": "Acumulación de tardanzas y tolerancia de ingreso",
        "categoria": "tardanzas",
        "texto_completo": (
            "Art. 13 – Acumulación de tardanzas y tolerancia de ingreso. "
            "La hora oficial de ingreso es a las 08:00 AM. Se otorga una "
            "tolerancia máxima de diez (10) minutos. Pasadas las 08:10 AM, "
            "el estudiante ingresará, pero se registrará como tardanza. La "
            "acumulación de tres (3) tardanzas injustificadas en un mismo "
            "período trimestral se computará automáticamente en el sistema "
            "como una (1) inasistencia injustificada para efectos de la "
            "calificación actitudinal."
        ),
        "reglas_clave": [
            "Hora de ingreso: 08:00 AM",
            "Tolerancia: 10 minutos (hasta 08:10 AM)",
            "Después de 08:10 AM → se registra como tardanza",
            "3 tardanzas injustificadas en 1 trimestre = 1 inasistencia injustificada",
        ],
        "hora_ingreso": "08:00",
        "tolerancia_minutos": 10,
        "hora_limite_tolerancia": "08:10",
        "tardanzas_para_falta": 3,
        "periodo_conversion": "trimestral",
    },

    # ── Art. 14: Representación institucional ─────────────────────────────────
    {
        "id": 14,
        "articulo": "Art. 14",
        "titulo": "Representación institucional, deportiva o cultural",
        "categoria": "representacion",
        "texto_completo": (
            "Art. 14 – Representación institucional, deportiva o cultural. "
            "Las inasistencias motivadas por la participación del estudiante "
            "en torneos deportivos, concursos académicos o eventos culturales "
            "en representación del colegio, de la región o del país, serán "
            "plenamente justificadas. Para que esta justificación sea válida, "
            "el apoderado debe tramitar el permiso como una 'Pre-falta' con "
            "al menos 48 horas de anticipación, adjuntando la carta de "
            "convocatoria de la federación, club o institución organizadora."
        ),
        "reglas_clave": [
            "Torneos, concursos, eventos culturales en representación → justificación plena",
            "Requiere trámite de 'Pre-falta' con 48h de anticipación",
            "Documento requerido: carta de convocatoria de la institución organizadora",
        ],
        "tipo_permiso": "pre_falta",
        "anticipacion_minima_horas": 48,
        "documento_requerido": "carta_convocatoria",
        "tipos_evento": ["torneo_deportivo", "concurso_academico", "evento_cultural"],
    },
]


# =============================================================================
#  CONFIGURACIÓN
# =============================================================================

COLLECTION_NAME = "reglamento_asistencia"
MODEL_NAME      = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE     = 384
QDRANT_HOST     = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT     = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY  = os.getenv("QDRANT_API_KEY") or None


# =============================================================================
#  HELPERS
# =============================================================================

def _get_qdrant() -> QdrantClient:
    """Retorna cliente Qdrant configurado.

    NOTA: https=False es obligatorio para instancias locales (docker-compose).
    qdrant-client >= 1.9 activa TLS automáticamente cuando se pasa api_key.
    """
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY,
        https=False,  # docker-compose local → HTTP plano
    )


def _get_model() -> SentenceTransformer:
    """Carga el modelo de embeddings (CPU-only)."""
    return SentenceTransformer(MODEL_NAME, device="cpu")


# =============================================================================
#  SEEDER PRINCIPAL
# =============================================================================

def seed_reglamento():
    """Crea/recrea la colección 'reglamento_asistencia' e inserta los artículos."""

    print("🚀 Iniciando seeding vectorial — Reglamento de Asistencia")
    print("=" * 55)
    print(f"   Qdrant:      {QDRANT_HOST}:{QDRANT_PORT}")
    print(f"   Colección:   {COLLECTION_NAME}")
    print(f"   Modelo:      {MODEL_NAME}  ({VECTOR_SIZE}d, cosine)")
    print(f"   Artículos:   {len(ARTICULOS_REGLAMENTO)} (Art. 10–14)")
    print("=" * 55)

    # ── 1. Conectar a Qdrant ──────────────────────────────────────────────────
    print("\n🔌 Conectando a Qdrant...")
    client = _get_qdrant()
    collections = [c.name for c in client.get_collections().collections]
    print(f"   Colecciones existentes: {collections}")

    # ── 2. Crear o recrear la colección ───────────────────────────────────────
    if COLLECTION_NAME in collections:
        print(f"   ⚠️  Colección '{COLLECTION_NAME}' ya existe → recreando...")
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )
    print(f"   ✅ Colección '{COLLECTION_NAME}' creada")

    # ── 3. Cargar modelo de embeddings ────────────────────────────────────────
    print("\n🧠 Cargando modelo de embeddings...")
    t0 = time.time()
    model = _get_model()
    print(f"   ✅ Modelo cargado en {time.time() - t0:.1f}s")

    # ── 4. Generar embeddings y construir puntos ──────────────────────────────
    print(f"\n📝 Generando embeddings para {len(ARTICULOS_REGLAMENTO)} artículos...")
    points = []

    for art in ARTICULOS_REGLAMENTO:
        # El texto que se vectoriza es el artículo completo
        embedding = model.encode(art["texto_completo"]).tolist()

        # Payload = todo excepto texto_completo (que ya está embebido) + texto_completo como referencia
        payload = {
            "articulo":       art["articulo"],
            "titulo":         art["titulo"],
            "categoria":      art["categoria"],
            "texto_completo": art["texto_completo"],
            "reglas_clave":   art["reglas_clave"],
        }

        # Agregar campos específicos de cada artículo al payload
        campos_extra = {
            k: v for k, v in art.items()
            if k not in ("id", "articulo", "titulo", "categoria", "texto_completo", "reglas_clave")
        }
        payload.update(campos_extra)

        points.append(PointStruct(
            id=art["id"],
            vector=embedding,
            payload=payload,
        ))

        print(f"   ✅ {art['articulo']} — {art['titulo']}")

    # ── 5. Upsert en Qdrant ───────────────────────────────────────────────────
    print(f"\n📤 Insertando {len(points)} puntos en Qdrant...")
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )

    # ── 6. Verificación ──────────────────────────────────────────────────────
    info = client.get_collection(COLLECTION_NAME)
    print(f"   ✅ Colección '{COLLECTION_NAME}': {info.points_count} puntos insertados")

    # ── 7. Test rápido de búsqueda semántica ──────────────────────────────────
    print("\n🔍 Test rápido de búsqueda semántica...")
    test_queries = [
        "El alumno faltó 3 días por enfermedad",
        "Hubo una inundación en Trujillo y no pudo llegar",
        "Falleció el abuelo del estudiante",
        "El alumno llega tarde todos los días",
        "Va a participar en un torneo de fútbol",
    ]

    for query in test_queries:
        query_vector = model.encode(query).tolist()
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=1,
        )
        if results.points:
            best = results.points[0]
            print(f"   🔎 \"{query}\"")
            print(f"      → {best.payload['articulo']} ({best.payload['categoria']}) — score: {best.score:.4f}")
        print()

    # ── Resumen final ─────────────────────────────────────────────────────────
    print("=" * 55)
    print("🎉 Seeding del reglamento completado exitosamente!")
    print("=" * 55)
    print(f"\n📊 Resumen:")
    print(f"   • Colección:  {COLLECTION_NAME}")
    print(f"   • Artículos:  {len(ARTICULOS_REGLAMENTO)}")
    for art in ARTICULOS_REGLAMENTO:
        print(f"     - {art['articulo']}: {art['titulo']} ({art['categoria']})")
    print(f"   • Dimensión:  {VECTOR_SIZE}")
    print(f"   • Distancia:  cosine")


# =============================================================================
#  ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    print("⏳ Esperando 10s a que Qdrant esté listo...")
    time.sleep(10)
    try:
        seed_reglamento()
    except Exception as e:
        print(f"\n❌ Seeding interrumpido: {e}")
        sys.exit(1)
    sys.exit(0)
