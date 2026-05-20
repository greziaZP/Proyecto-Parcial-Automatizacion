import os
import json
import logging
from typing import Any
from app.state.shared_state import SharedState
import anthropic

logger = logging.getLogger("OrquestadorAgent")

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

    def orchestrate(self, state: SharedState) -> SharedState:
        """
        Decide qué agente debe actuar a continuación basado en el estado actual.
        """
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("❌ ANTHROPIC_API_KEY no configurada en las variables de entorno.")
                return state

            client = anthropic.Anthropic(api_key=api_key)
            
            # Convertir estado a dict para serializarlo en el mensaje
            state_dict = state.model_dump()
            # También incluir campos dinámicos si existen en __dict__
            state_dict.update({k: v for k, v in state.__dict__.items() if k not in state_dict})

            user_message = (
                f"Estado actual de la memoria compartida (SharedState):\n"
                f"{json.dumps(state_dict, indent=2, default=str)}\n\n"
                f"Decide qué agente debe actuar a continuación. Responde ÚNICAMENTE con "
                f"una de estas palabras clave en minúsculas y sin comillas:\n"
                f"- 'analista'\n"
                f"- 'evaluador'\n"
                f"- 'mediador'\n"
                f"- 'done'"
            )

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            response_text = message.content[0].text.strip().lower()
            
            # Limpiar posibles comillas o espacios de la respuesta
            decision = "".join(c for c in response_text if c.isalnum() or c == "_")
            
            if decision not in ["analista", "evaluador", "mediador", "done"]:
                logger.warning(f"⚠️ Decisión de enrutamiento inesperada: '{decision}'. Usando 'analista' por defecto.")
                decision = "analista"

            logger.info(f"➡️ Agente Orquestador decidió enrutar a: '{decision}'")
            object.__setattr__(state, "next_agent", decision)
            return state

        except Exception as e:
            logger.error(f"❌ Error en OrquestadorAgent.orchestrate: {e}", exc_info=True)
            # Valor por defecto ante error
            object.__setattr__(state, "next_agent", "analista")
            return state

    def process_message(self, mensaje: str, state: SharedState) -> SharedState:
        """Punto de entrada compatible con la versión anterior."""
        return self.orchestrate(state)

    def handoff(self, target_agent: str, state: SharedState) -> SharedState:
        """Traspasa el control a otro agente especializado."""
        object.__setattr__(state, "next_agent", target_agent)
        return state
