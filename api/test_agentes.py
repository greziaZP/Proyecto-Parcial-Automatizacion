import sys
import uuid
import os
from dotenv import load_dotenv

# Cargar las variables de entorno para AI_MODEL_API_KEY y credenciales PostgreSQL / Qdrant
load_dotenv(dotenv_path="../.env")

# Asegurar importaciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.state.shared_state import SharedState
from app.agents.orquestador import OrquestadorAgent

def test_swarm():
    # Asegurarnos de que el API key de OpenAI esté configurado antes de lanzar el test
    if not os.getenv("AI_MODEL_API_KEY"):
        print("⚠️  Es necesario definir AI_MODEL_API_KEY en tu archivo .env para realizar esta prueba.")
        return

    # Usamos identificadores quemados de ejemplo solo para la prueba en la terminal
    from datetime import date
    estado_inicial = SharedState(
        alumno_id="b319354c-d876-4231-a69c-97e87c776646",
        incidencia_id=str(uuid.uuid4()),
        padre_id=str(uuid.uuid4()),  # Simulamos un padre en la DB
        tipo_flujo="JUSTIFICACION_MEDICA",
        estado_actual="INICIO",
        fecha_actual=str(date.today())
    )

    mensaje_usuario = "Soy el padre del estudiante, quiero justificar porque hoy amaneció enfermo y se fue al seguro."

    print("\n🚀 Iniciando prueba del SWARM LLM... (Orquestador al mando)\n")
    
    orquestador = OrquestadorAgent()
    estado_final = orquestador.ejecutar(estado_inicial, mensaje_usuario)

    print("\n✅ SWARM FINALIZADO. MEMORIA COMPARTIDA RESULTANTE:")
    print("=" * 60)
    print(f"Analisis Conductual: {estado_final.analisis_conductual}")
    print(f"Normativa Encontrada: {estado_final.resultado_rag_reglamento}")
    print(f"Dictamen Final (Mediador): {estado_final.dictamen_final}")
    print("=" * 60)
    print(f"Llamadas MCP registradas: {estado_final.mcp_logs}")

if __name__ == "__main__":
    test_swarm()
