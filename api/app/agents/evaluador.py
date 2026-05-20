import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState
from app.mcp.vector_tools import consultar_reglamento
from app.mcp.schemas import ConsultarReglamentoInput

class EvaluadorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.system_prompt = """
        Eres el Agente Evaluador Normativo. Tu función es puramente legal e institucional.

        Debes tomar el mensaje de justificación que envió el padre de familia (disponible en el contexto del flujo) y pasarlo como query a la herramienta consultar_reglamento.

        Analiza los artículos devueltos por la herramienta y redacta un informe en el campo resultado_rag_reglamento indicando qué artículos aplican a la situación (ej. plazos de 48 horas, requisitos de certificados médicos, etc.). No inventes reglas, básate solo en lo que devuelva la herramienta.
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

    def ejecutar(self, state: SharedState) -> SharedState:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"El análisis conductual dice:\n{state.analisis_conductual}\n\nRevisa el reglamento para este caso."}
        ]

        while True:
            response = self.client.chat.completions.create(
                model="gemini-1.5-flash",
                messages=messages,
                tools=self.tools,
                temperature=0.2
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_unset=True))

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "consultar_reglamento":
                        args = json.loads(tool_call.function.arguments)
                        try:
                            input_data = ConsultarReglamentoInput(query=args["query"])
                            tool_result = consultar_reglamento(input_data)
                            result_str = tool_result.model_dump_json()
                        except Exception as e:
                            result_str = f"Error MCP: {str(e)}"
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_str
                        })
                        state.mcp_logs.append({"tool": "consultar_reglamento", "args": args})
            else:
                state.resultado_rag_reglamento = msg.content
                break
        
        return state
