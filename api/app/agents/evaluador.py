from app.state.shared_state import SharedState

class EvaluadorAgent:
    def __init__(self):
        self.system_prompt = """
        Eres el Agente Evaluador Normativo, experto en RAG y reglamentos del 
        Colegio Rafael Narváez Cadenillas.
        
        Alcance:
        1. Recibirás en el SharedState el contexto de la incidencia y quizás el
           'analisis_conductual' previo.
        2. Tu misión es contrastar esta situación con las normas institucionales.
        3. DEBES invocar OBLIGATORIAMENTE la herramienta MCP 'consultar_reglamento'
           (Base de Datos Vectorial) usando los términos clave del problema (ej."falta médica", 
           "suspensión").
        4. Consolida la normativa aplicable extraida y determina si el caso en cuestión
           es sancionable, perdonable o si requiere derivación al psicólogo institucional.
        5. Escribe un resumen de tu evaluación en 'resultado_rag_reglamento' dentro 
           del SharedState.
        6. Devuelve el control al Agente Orquestador.
        """

    def evaluate(self, state: SharedState) -> SharedState:
        """
        Consulta reglamento vía Vector DB, analiza normativas y guarda en 'resultado_rag_reglamento'.
        """
        raise NotImplementedError("Database connection not yet implemented")
