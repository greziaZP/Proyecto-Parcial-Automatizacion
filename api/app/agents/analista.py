import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState
from app.mcp.postgres_tools import mcp_buscar_historial_estudiante
from app.mcp.schemas import BuscarHistorialInput

ANALISTA_FORCED_PROMPT = """Con base en los datos obtenidos del historial, redacta un perfil conductual del estudiante en lenguaje natural. Incluye:
- Cuántas faltas y tardanzas tiene en el periodo actual.
- Si tiene acumulados relevantes (nota actitudinal).
- Si es reincidente o tiene un historial limpio.
- Una evaluación cualitativa clara (ej: "Perfil confiable", "Alumno con inasistencias frecuentes").
No seas genérico, usa los datos reales que obtuviste."""

class AnalistaAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.system_prompt = """
        Eres el Agente Analista Conductual del Colegio Rafael Narváez Cadenillas. Tu misión es construir un perfil de asistencia y comportamiento del estudiante basado en datos históricos reales.
        
        Paso 1: Invoca la herramienta 'mcp_buscar_historial_estudiante' pasándole el 'estudiante_uid'.
        Paso 2: Con los datos reales devueltos, redacta un análisis que incluya:
        - Cuántas faltas y tardanzas tiene el estudiante en el periodo actual.
        - Si tiene acumulados relevantes (nota actitudinal).
        - Si es reincidente o si tiene un historial limpio.
        - Una evaluación cualitativa: "Perfil confiable", "Alumno con inasistencias frecuentes", etc.
        
        Sé directo pero objetivo. Usa los datos reales, no inventes.
        """
        self.tools = [{
            "type": "function",
            "function": {
                "name": "mcp_buscar_historial_estudiante",
                "description": "Busca el historial real de asistencia y comportamiento de un estudiante en PostgreSQL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "estudiante_uid": {"type": "string", "description": "UUID del estudiante"}
                    },
                    "required": ["estudiante_uid"]
                }
            }
        }]

    def ejecutar(self, state: SharedState) -> SharedState:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"SharedState actual: {state.model_dump_json(indent=2)}\n\nAnaliza este ID: {state.alumno_id}"}
        ]

        while True:
            print(f"\n[ANALISTA] Pensando... (Mensajes en historial: {len(messages)})")
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-lite",
                messages=messages,
                tools=self.tools,
                temperature=0.2
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_unset=True))

            if msg.tool_calls:
                print(f"[ANALISTA] Herramientas invocadas: {[t.function.name for t in msg.tool_calls]}")
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "mcp_buscar_historial_estudiante":
                        args = json.loads(tool_call.function.arguments)
                        print(f"[ANALISTA] Ejecutando mcp_buscar_historial_estudiante con args: {args}")
                        try:
                            input_data = BuscarHistorialInput(estudiante_uid=args["estudiante_uid"])
                            tool_result = mcp_buscar_historial_estudiante(input_data)
                            result_str = tool_result.model_dump_json()
                        except Exception as e:
                            result_str = f"Error MCP: {str(e)}"
                            print(f"[ANALISTA] Error ejecutando herramienta: {e}")
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_str
                        })
                        state.mcp_logs.append({"tool": "mcp_buscar_historial_estudiante", "args": args})
            else:
                break

        final_text = msg.content
        if not final_text:
            print("[ANALISTA] LLM no generó texto, forzando redacción...")
            messages.append({"role": "user", "content": ANALISTA_FORCED_PROMPT})
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-lite",
                messages=messages,
                temperature=0.3
            )
            final_text = response.choices[0].message.content

        print(f"[ANALISTA] Guardando análisis textual: {final_text}")
        state.analisis_conductual = final_text
        return state