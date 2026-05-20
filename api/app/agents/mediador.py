import json
import os
from openai import OpenAI
from app.state.shared_state import SharedState
from app.mcp.postgres_tools import mcp_registrar_citacion, mcp_gestionar_justificacion
from app.mcp.schemas import RegistrarCitacionInput, GestionarJustificacionInput

MEDIADOR_FORCED_PROMPT = """Ahora redacta tu dictamen final como mensaje directo al padre. NO uses formato de carta ni saludos formales tipo "Estimado padre" ni firmas tipo "Atentamente, Agente Mediador".Habla de tú, de forma cercana y natural, como si fuera un chat. Varía la estructura y el tono según el caso —a veces más breve, a veces más detallado—. Explica la decisión, los artículos que aplican y los pasos a seguir, pero sin sonar como plantilla."""

class MediadorAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("AI_MODEL_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.system_prompt = """
        Eres el asistente virtual del Colegio Rafael Narváez Cadenillas que atiende a los padres de familia. Tienes autoridad para registrar justificaciones y citaciones en el sistema.

        Debes leer el analisis_conductual (historial de faltas del alumno) y el resultado_rag_reglamento (las normas institucionales).

        Toma de decisiones:
        1. Si el alumno tiene un historial limpio y el reglamento ampara la excusa del padre, DEBES INVOCAR OBLIGATORIAMENTE la herramienta 'mcp_gestionar_justificacion' para registrar la falta como aprobada.
        2. Puedes y debes registrar justificaciones de forma preventiva (ej. antes de que inicie la clase o si el alumno aún no tiene falta registrada). NUNCA le pidas al padre "el ID de la asistencia" ni ningún otro ID. Registra la justificación con los datos disponibles OBLIGATORIAMENTE.
        3. Si la excusa viola los plazos o el alumno es reincidente, INVOCA 'mcp_gestionar_justificacion' con estado 'rechazada' Y LUEGO INVOCA 'mcp_registrar_citacion'.

        VALORES EXACTOS para tipo_justificacion (enum de PostgreSQL):
        - "medica"   (enfermedad, certificado médico)
        - "familiar" (fallecimiento, urgencia familiar)
        - "viaje"    (viaje autorizado)
        - "otra"     (cualquier otro motivo)

        NUNCA uses valores como "JUSTIFICACION_MEDICA". Usa SIEMPRE los valores en minúsculas: medica, familiar, viaje, otra.

        DESPUÉS de invocar las herramientas, DEBES redactar un dictamen_final como respuesta directa al padre en un chat. Reglas de estilo:
        - NO uses formato de carta, NOUses saludos como "Estimado padre de familia", NOUses firmas como "Atentamente, Agente Mediador".
        - Habla de tú, de forma cercana y natural, como si conversaras por WhatsApp.
        - VARÍA la estructura y longitud de cada respuesta. A veces responde breve, a veces más detallado. NUNCA uses la misma estructura dos veces.
        - Explica la decisión, los artículos que aplican y los pasos a seguir, pero con naturalidad.
        - Indica claramente si la justificación fue aprobada, rechazada o está pendiente.
        - Si se requiere alguna acción adicional (adjuntar certificado, asistir a citación), menciónalo de forma casual.
        - Personaliza según el historial del alumno y las normas que aplican. NUNCA repitas la misma redacción.

        IMPORTANTE: NO DEBES escribir el resultado de la función en formato JSON. DEBES usar el sistema de Tools/Function Calling para activar las funciones reales con los UUID del estado.
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
                    "description": "Registra una justificación de incidencia formal. Valores permitidos para tipo_justificacion: medica, familiar, viaje, otra.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "padre_solicitante_uid": {"type": "string"},
                            "tipo_justificacion": {"type": "string", "enum": ["medica", "familiar", "viaje", "otra"]},
                            "fecha_inicio_incidencia": {"type": "string", "format": "date"},
                            "fecha_fin_incidencia": {"type": "string", "format": "date"},
                            "descripcion_motivo": {"type": "string"},
                            "estado_justificacion": {"type": "string", "enum": ["pendiente", "aprobada", "rechazada"], "description": "Estado de la justificación. Usar 'aprobada' si el reglamento ampara, 'rechazada' si no."}
                        },
                        "required": ["padre_solicitante_uid", "tipo_justificacion", "fecha_inicio_incidencia", "fecha_fin_incidencia", "descripcion_motivo", "estado_justificacion"]
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
                            if tool_result.justificacion_uid:
                                state.justificacion_uid = str(tool_result.justificacion_uid)
                        
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
                break

        final_text = msg.content
        if not final_text:
            print("[MEDIADOR] LLM no generó texto, forzando redacción...")
            messages.append({"role": "user", "content": MEDIADOR_FORCED_PROMPT})
            response = self.client.chat.completions.create(
                model="gemini-2.5-flash-lite",
                messages=messages,
                temperature=0.3
            )
            final_text = response.choices[0].message.content

        print(f"[MEDIADOR] Emitiendo dictamen final: {final_text}")
        state.dictamen_final = final_text
        return state