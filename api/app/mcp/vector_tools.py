import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from app.mcp.schemas import ConsultarReglamentoInput, ConsultarReglamentoOutput

# Instanciar el modelo de embeddings a nivel de módulo (cacheado en memoria)
encoder = SentenceTransformer('all-MiniLM-L6-v2')

# Configurar Qdrant Client conectando al servicio local
qdrant_host = os.getenv("QDRANT_HOST", "localhost")
qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
client = QdrantClient(host=qdrant_host, port=qdrant_port)

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
            contenido = payload.get("texto", "")
            
            articulos.append(articulo_titulo)
            textos.append(f"[{articulo_titulo}]: {contenido}")
            
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
