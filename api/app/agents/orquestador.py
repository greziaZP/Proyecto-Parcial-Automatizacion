from typing import Any
from app.state.shared_state import SharedState

class OrquestadorAgent:
    def __init__(self):
        self.system_prompt = """
        Eres el Agente Orquestador, el coordinador principal del Swarm Multiagente para el 
        sistema de gestión del Colegio Rafael Narváez Cadenillas. Tu objetivo es enrutar 
        las solicitudes entrantes hacia el agente especializado correspondiente y manejar 
        el flujo de la arquitectura.

        Responsabilidades:
        1. Recibir la solicitud inicial del usuario o disparador del Event Bus.
        2. Leer el 'tipo_flujo' y el 'estado_actual' del SharedState.
        3. Invocar al Agente Analista si se necesita recopilar contexto histórico.
        4. Invocar al Agente Evaluador si el dictamen requiere comparar con reglamentos.
        5. Invocar al Agente Mediador si se requiere una resolución, sanción o justificación final.
        6. Si el flujo ha concluido, llamar a la herramienta MCP 'registrar_citacion' (si aplica) 
           y devolver una respuesta consolidada al usuario.
        
        Reglas estables:
        - Nunca asumas el rol de los agentes especializados.
        - Limítate a delegar y centralizar los resultados.
        - Todo traspaso de información entre agentes debe mutar el objeto SharedState.
        """

    def process_message(self, mensaje: str, state: SharedState) -> SharedState:
        """
        Punto de entrada para evaluar la intención del usuario y determinar la ruta.
        """
        raise NotImplementedError("Database connection not yet implemented")

    def handoff(self, target_agent: str, state: SharedState) -> SharedState:
        """
        Traspasa el control a otro agente especializado, pasándole la memoria compartida.
        """
        raise NotImplementedError("Database connection not yet implemented")
