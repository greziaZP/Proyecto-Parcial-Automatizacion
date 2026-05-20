import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState
from app.mcp.postgres_tools import mcp_registrar_citacion, mcp_gestionar_justificacion
from app.mcp.schemas import RegistrarCitacionInput, GestionarJustificacionInput

class MediadorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"))
        self.system_prompt = """
        Eres el Agente Mediador y Resolutor de Conflictos. Tienes la máxima autoridad para alterar la base de datos del colegio.

        Debes leer el analisis_conductual (historial de faltas del alumno en Postgres) y el resultado_rag_reglamento (las normas institucionales).

        Toma de decisiones:
        1. Si el alumno tiene un historial limpio y el reglamento ampara la excusa del padre, invoca mcp_gestionar_justificacion para registrar la falta como 'aprobada'.
        2. Si la excusa viola los plazos del reglamento o el alumno es un reincidente crítico según el análisis conductual, deniega la justificación llamando a mcp_gestionar_justificacion con estado 'rechazada' e invoca inmediatamente mcp_registrar_citacion para obligar al padre a una reunión presencial con psicopedagogía.

        Redacta el veredicto final detallado en el campo dictamen_final.
        """
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "mcp_registrar_citacion",
                    "description": "Registra una citación presencial con apoderados.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "estudiante_uid": {"type": "string"},
                            "padre_apoderado_uid": {"type": "string"},
                            "docente_solicitante_uid": {"type": "string"},
                            "motivo": {"type": "string"},
                            "fecha_citacion": {"type": "string", "description": "Formato ISO ISO8601, ej: 2026-05-20T10:00:00"}
                        },
                        "required": ["estudiante_uid", "padre_apoderado_uid", "docente_solicitante_uid", "motivo", "fecha_citacion"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_gestionar_justificacion",
                    "description": "Registra una justificación de incidencia formal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "padre_solicitante_uid": {"type": "string"},
                            "tipo_justificacion": {"type": "string"},
                            "fecha_inicio_incidencia": {"type": "string", "format": "date"},
                            "fecha_fin_incidencia": {"type": "string", "format": "date"},
                            "descripcion_motivo": {"type": "string"}
                        },
                        "required": ["padre_solicitante_uid", "tipo_justificacion", "fecha_inicio_incidencia", "fecha_fin_incidencia", "descripcion_motivo"]
                    }
                }
            }
        ]

    def ejecutar(self, state: SharedState) -> SharedState:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"El estado completo es: {state.model_dump_json(indent=2)}\n\nToma una decisión final y activa la herramienta que corresponda."}
        ]

        while True:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=self.tools,
                temperature=0.2
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_unset=True))

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    args = json.loads(tool_call.function.arguments)
                    try:
                        if tool_call.function.name == "mcp_registrar_citacion":
                            input_data = RegistrarCitacionInput(**args)
                            tool_result = mcp_registrar_citacion(input_data)
                        elif tool_call.function.name == "mcp_gestionar_justificacion":
                            input_data = GestionarJustificacionInput(**args)
                            tool_result = mcp_gestionar_justificacion(input_data)
                        
                        result_str = tool_result.model_dump_json()
                    except Exception as e:
                        result_str = f"Error MCP: {str(e)}"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str
                    })
                    state.mcp_logs.append({"tool": tool_call.function.name, "args": args})
            else:
                state.dictamen_final = msg.content
                break
        
        return state
