import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState
from app.mcp.vector_tools import consultar_reglamento
from app.mcp.schemas import ConsultarReglamentoInput

EVALUADOR_FORCED_PROMPT = """Con base en los artículos del reglamento devueltos por la búsqueda, redacta un informe normativo detallado. Indica:
- Qué artículos del reglamento aplican a la situación (con su número y título).
- Las reglas clave de cada artículo aplicable.
- Si la solicitud del padre cumple o no con cada requisito del reglamento.
- Una conclusión clara sobre si el reglamento ampara o no la justificación.
No inventes reglas, básate solo en lo que devolvió la herramienta."""

class EvaluadorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.system_prompt = """
        Eres el Agente Evaluador Normativo del Colegio Rafael Narváez Cadenillas. Tu función es puramente legal e institucional.

        Debes tomar el mensaje de justificación que envió el padre de familia y pasarlo como query a la herramienta consultar_reglamento.

        Analiza los artículos devueltos por la herramienta y redacta un informe DETALLADO en resultado_rag_reglamento que incluya:
        - Qué artículos del reglamento aplican a la situación (con su número y título).
        - Las reglas clave de cada artículo aplicable.
        - Si la justificación del padre cumple o no con cada requisito del reglamento.
        - Conclusión clara sobre si el reglamento ampara o no la solicitud.

        No inventes reglas, básate SOLO en lo que devuelva la herramienta. Pero sí redacta en lenguaje natural, dirigido al equipo del colegio.
        """
        self.tools = [{
            "type": "function",
            "function": {
                "name": "consultar_reglamento",
                "description": "Realiza una búsqueda semántica en la BD Vectorial sobre normas de la institución.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Consulta de lenguaje natural, ej: 'ausencia injustificada'"}
                    },
                    "required": ["query"]
                }
            }
        }]

    def ejecutar(self, state: SharedState, mensaje: str = "") -> SharedState:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"El padre solicita: '{mensaje}'\n\nEl análisis conductual dice:\n{state.analisis_conductual}\n\nRevisa el reglamento para este caso."}
        ]

        while True:
            print(f"\n[EVALUADOR] Pensando... (Mensajes en historial: {len(messages)})")
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-lite",
                messages=messages,
                tools=self.tools,
                temperature=0.2
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_unset=True))

            if msg.tool_calls:
                print(f"[EVALUADOR] Herramientas invocadas: {[t.function.name for t in msg.tool_calls]}")
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "consultar_reglamento":
                        args = json.loads(tool_call.function.arguments)
                        print(f"[EVALUADOR] Ejecutando consultar_reglamento con args: {args}")
                        try:
                            input_data = ConsultarReglamentoInput(query=args["query"])
                            tool_result = consultar_reglamento(input_data)
                            result_str = tool_result.model_dump_json()
                        except Exception as e:
                            print(f"[EVALUADOR] Error ejecutando herramienta: {e}")
                            result_str = f"Error MCP: {str(e)}"
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_str
                        })
                        state.mcp_logs.append({"tool": "consultar_reglamento", "args": args})
            else:
                break

        final_text = msg.content
        if not final_text:
            print("[EVALUADOR] LLM no generó texto, forzando redacción...")
            messages.append({"role": "user", "content": EVALUADOR_FORCED_PROMPT})
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-lite",
                messages=messages,
                temperature=0.3
            )
            final_text = response.choices[0].message.content

        print(f"[EVALUADOR] Finalizó la consulta al reglamento: {final_text}")
        state.resultado_rag_reglamento = final_text
        return state