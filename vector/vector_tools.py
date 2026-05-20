"""
vector/vector_tools.py
======================
Herramientas de consulta vectorial para el reglamento institucional.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vector_tools")

# Cargar variables de entorno desde el archivo .env en la raíz del proyecto
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# Nombre de la colección en Qdrant
COL_REGLAMENTO = "reglamento_institucional"

# Singleton para el modelo de embeddings
_model_instance = None

def _get_model() -> SentenceTransformer:
    """Retorna la instancia única del modelo de embeddings (Singleton)."""
    global _model_instance
    if _model_instance is None:
        logger.info("🧠 Cargando modelo de embeddings (all-MiniLM-L6-v2) en singleton...")
        _model_instance = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_instance


def consultar_reglamento(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Realiza una búsqueda semántica en la colección del reglamento institucional.

    Args:
        query (str): Texto de la consulta o situación a evaluar.
        top_k (int): Cantidad máxima de artículos relevantes a retornar.

    Returns:
        List[Dict[str, Any]]: Lista de diccionarios con el formato:
            {
                "articulo": "Art. X",
                "contenido": "Texto del artículo...",
                "score": float (redondeado a 4 decimales)
            }
    """
    if not query or not query.strip():
        logger.warning("⚠️ Consulta vacía recibida en consultar_reglamento.")
        return []

    try:
        # 1. Obtener cliente Qdrant con variables de entorno
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        api_key = os.getenv("QDRANT_API_KEY") or None

        client = QdrantClient(
            host=host,
            port=port,
            api_key=api_key,
            https=False,  # Forzar HTTP plano en local
        )

        # 2. Verificar que la colección existe
        if not client.collection_exists(COL_REGLAMENTO):
            logger.warning(f"⚠️ La colección '{COL_REGLAMENTO}' no existe en Qdrant.")
            return []

        # 3. Codificar la consulta usando el modelo de embeddings
        model = _get_model()
        query_vector = model.encode(query).tolist()

        # 4. Realizar la búsqueda semántica
        # Soporta tanto query_points (API unificada moderna) como search (API tradicional)
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=COL_REGLAMENTO,
                query=query_vector,
                limit=top_k,
            )
            points = response.points
        elif hasattr(client, "search"):
            points = client.search(
                collection_name=COL_REGLAMENTO,
                query_vector=query_vector,
                limit=top_k,
            )
        else:
            logger.error("❌ El cliente Qdrant no posee un método de consulta compatible.")
            return []

        # 5. Formatear y retornar los resultados
        resultados = []
        for point in points:
            payload = point.payload or {}
            # Leer el contenido desde 'texto' o 'contenido'
            contenido = payload.get("texto") or payload.get("contenido") or ""
            articulo = payload.get("articulo") or "Sin Art."
            
            resultados.append({
                "articulo": articulo,
                "contenido": contenido,
                "score": round(float(point.score), 4),
            })

        return resultados

    except Exception as e:
        logger.error(f"❌ Error al consultar Qdrant o realizar búsqueda RAG: {e}", exc_info=True)
        return []
