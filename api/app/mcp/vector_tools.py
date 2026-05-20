import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from app.mcp.schemas import ConsultarReglamentoInput, ConsultarReglamentoOutput

encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

qdrant_host = os.getenv("QDRANT_HOST", "localhost")
qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
client = QdrantClient(host=qdrant_host, port=qdrant_port, api_key=qdrant_api_key, https=False)

def consultar_reglamento(input_data: ConsultarReglamentoInput) -> ConsultarReglamentoOutput:
    """
    Realiza una búsqueda semántica (RAG) en la Base de Datos Vectorial sobre el reglamento 
    y normas del Colegio Rafael Narváez Cadenillas.
    """
    try:
        # Generar embedding de la búsqueda (query)
        query_vector = encoder.encode(input_data.query).tolist()
        
        # Búsqueda semántica en Qdrant
        search_result = client.search(
            collection_name="reglamento_asistencia",
            query_vector=query_vector,
            limit=3
        )
        
        articulos = []
        textos = []
        
        # Extraer resultados
        for hit in search_result:
            payload = hit.payload or {}
            articulo_titulo = payload.get("articulo", "Artículo Desconocido")
            contenido = payload.get("texto_completo", "") or payload.get("texto", "")
            reglas = payload.get("reglas_clave", [])
            reglas_str = "\n  - ".join(reglas) if reglas else ""

            articulos.append(articulo_titulo)
            entrada = f"[{articulo_titulo} — {payload.get('titulo', '')}]: {contenido}"
            if reglas_str:
                entrada += f"\n  Reglas clave:\n  - {reglas_str}"
            textos.append(entrada)
            
        contexto_concatenado = "\n".join(textos) if textos else "No se encontraron normativas que coincidan con la búsqueda."
        
        return ConsultarReglamentoOutput(
            articulos_relevantes=articulos,
            contexto_extraido=contexto_concatenado
        )
        
    except Exception as e:
        return ConsultarReglamentoOutput(
            articulos_relevantes=[],
            contexto_extraido=f"Error al consultar la base de datos vectorial (Qdrant): {str(e)}"
        )
