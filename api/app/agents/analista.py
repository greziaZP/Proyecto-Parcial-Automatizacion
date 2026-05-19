from app.state.shared_state import SharedState

class AnalistaAgent:
    def __init__(self):
        self.system_prompt = """
        Eres el Agente Analista Conductual. Tu única misión es construir un perfil 
        de asistencia y comportamiento del estudiante basado en datos históricos.
        
        Alcance:
        1. Recibirás el 'alumno_id' a través del SharedState.
        2. DEBES invocar OBLIGATORIAMENTE la herramienta MCP 'buscar_historial' para
           extraer la data dura de PostgreSQL.
        3. Una vez recibidos los datos, deberás analizar tendencias: ¿Existen inasistencias
           repetitivas los lunes? ¿Tiene buen comportamiento general?
        4. No debes emitir juicios de valor ni decidir sobre reglas.
        5. Escribe tus hallazgos en la variable 'analisis_conductual' del SharedState.
        6. Una vez escrito, devuelve el control al Agente Orquestador.
        """

    def analyze(self, state: SharedState) -> SharedState:
        """
        Extrae datos vía MCP, analiza y muta el 'analisis_conductual' en el SharedState.
        """
        raise NotImplementedError("Database connection not yet implemented")
