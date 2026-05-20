import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState
from app.mcp.postgres_tools import mcp_registrar_citacion, mcp_gestionar_justificacion
from app.mcp.schemas import RegistrarCitacionInput, GestionarJustificacionInput

class MediadorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.system_prompt = """
        Eres el Agente Mediador y Resolutor de Conflictos. Tienes la máxima autoridad para alterar la base de datos del colegio.

        Debes leer el analisis_conductual (historial de faltas del alumno en Postgres) y el resultado_rag_reglamento (las normas institucionales).

        Toma de decisiones:
        1. Si el alumno tiene un historial limpio y el reglamento ampara la excusa del padre, DEBES INVOCAR OBLIGATORIAMENTE la herramienta 'mcp_gestionar_justificacion' para registrar la falta como aprobada.
        2. Si la excusa viola los plazos o el alumno es reincidente, INVOCA 'mcp_gestionar_justificacion' con estado 'rechazada' Y LUEGO INVOCA 'mcp_registrar_citacion'.

        IMPORTANTE: NO DEBES escribir el resultado de la función en formato JSON plano en tu texto. DEBES usar el sistema de Tools/Function Calling para activar las funciones reales con los UUID que se te proporcionan en estado completo (como padre_id, incidencia_id que se mapea a asistencia_clase_uid, etc).
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

    def ejecutar(self, state: SharedState, mensaje: str = "") -> SharedState:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Mensaje original del padre: '{mensaje}'\n\nEl estado completo es: {state.model_dump_json(indent=2)}\n\nToma una decisión final y activa la herramienta que corresponda OBLIGATORIAMENTE."}
        ]

        while True:
            print(f"\n[MEDIADOR] Pensando... (Mensajes en historial: {len(messages)})")
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-lite",
                messages=messages,
                tools=self.tools,
                temperature=0.2
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_unset=True))

            if msg.tool_calls:
                print(f"[MEDIADOR] Herramientas invocadas: {[t.function.name for t in msg.tool_calls]}")
                for tool_call in msg.tool_calls:
                    args = json.loads(tool_call.function.arguments)
                    print(f"[MEDIADOR] Ejecutando {tool_call.function.name} con args: {args}")
                    try:
                        if tool_call.function.name == "mcp_registrar_citacion":
                            input_data = RegistrarCitacionInput(**args)
                            tool_result = mcp_registrar_citacion(input_data)
                        elif tool_call.function.name == "mcp_gestionar_justificacion":
                            input_data = GestionarJustificacionInput(**args)
                            tool_result = mcp_gestionar_justificacion(input_data)
                        
                        result_str = tool_result.model_dump_json()
                    except Exception as e:
                        print(f"[MEDIADOR] Error ejecutando herramienta: {e}")
                        result_str = f"Error MCP: {str(e)}"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str
                    })
                    state.mcp_logs.append({"tool": tool_call.function.name, "args": args})
            else:
                final_text = msg.content or "Resolución ejecutada por el agente Mediador."
                print(f"[MEDIADOR] Emitiendo dictamen final: {final_text}")
                state.dictamen_final = final_text
                break
        
        return state
