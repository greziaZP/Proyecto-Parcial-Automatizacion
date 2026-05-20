import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState

from app.agents.analista import AnalistaAgent
from app.agents.evaluador import EvaluadorAgent
from app.agents.mediador import MediadorAgent

class OrquestadorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"))
        self.system_prompt = """
        Eres el Agente Orquestador. Basado en el SharedState y el mensaje del usuario, 
        debes determinar cuál es el próximo Agente a invocar utilizando tu herramienta de enrutamiento, o devolver el resultado final.
        
        Tus opciones válidas son: ["Analista", "Evaluador", "Mediador", "Finalizar"]
        
        Flujo normal:
        Usuario reporta falta -> Analista (ve el historial) -> Evaluador (ve las reglas) -> Mediador (registra citación/permiso) -> Finalizar.
        """
        self.tools = [{
            "type": "function",
            "function": {
                "name": "handoff",
                "description": "Enruta la petición al siguiente agente especializado.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_agent": {"type": "string", "enum": ["Analista", "Evaluador", "Mediador", "Finalizar"]}
                    },
                    "required": ["target_agent"]
                }
            }
        }]

    def ejecutar(self, state: SharedState, mensaje: str = None) -> SharedState:
        # Se requiere orquestar repetidamente hasta Finalizar
        while True:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Mensaje usuario: {mensaje}\nSharedState:\n{state.model_dump_json(indent=2)}"}
            ]

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=self.tools,
                tool_choice={"type": "function", "function": {"name": "handoff"}},
                temperature=0.0
            )

            msg = response.choices[0].message
            target_agent = "Finalizar"
            if msg.tool_calls:
                args = json.loads(msg.tool_calls[0].function.arguments)
                target_agent = args.get("target_agent", "Finalizar")
            
            state.estado_actual = target_agent

            if target_agent == "Finalizar":
                break
            elif target_agent == "Analista":
                print("==> Transfiriendo a Agente Analista...")
                state = AnalistaAgent().ejecutar(state)
            elif target_agent == "Evaluador":
                print("==> Transfiriendo a Agente Evaluador...")
                state = EvaluadorAgent().ejecutar(state)
            elif target_agent == "Mediador":
                print("==> Transfiriendo a Agente Mediador...")
                state = MediadorAgent().ejecutar(state)
            
        return state
