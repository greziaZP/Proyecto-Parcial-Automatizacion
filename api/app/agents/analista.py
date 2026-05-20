import os
import json
import logging
from app.state.shared_state import SharedState
import anthropic

logger = logging.getLogger("AnalistaAgent")

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

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    def analyze(self, state: SharedState) -> SharedState:
        """
        Extrae datos, analiza y muta el 'analisis' y 'analisis_conductual' en el SharedState.
        """
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("❌ ANTHROPIC_API_KEY no configurada.")
                return state

            client = anthropic.Anthropic(api_key=api_key)

            # Obtener datos de la fuga/inasistencia
            fuga_record = getattr(state, "fuga_record", None)
            if not fuga_record:
                # Fallback al estado general
                fuga_record = {
                    "alumno_id": state.alumno_id,
                    "incidencia_id": state.incidencia_id,
                    "tipo_flujo": state.tipo_flujo,
                    "estado_actual": state.estado_actual
                }

            user_message = (
                f"Datos de la fuga/inasistencia (fuga_record):\n"
                f"{json.dumps(fuga_record, indent=2, default=str)}\n\n"
                f"Por favor realiza un análisis conductual estructurado. "
                f"Responde ÚNICAMENTE con un objeto JSON válido con las siguientes claves:\n"
                f"- 'nivel_riesgo': string ('bajo', 'medio' o 'alto')\n"
                f"- 'patron_detectado': boolean (true si hay patrón recurrente, false en caso contrario)\n"
                f"- 'resumen': string (análisis detallado de la conducta e inasistencias)\n"
                f"No agregues texto introductorio ni explicaciones fuera del JSON."
            )

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            response_text = message.content[0].text.strip()
            analisis_json = self._parse_json(response_text)

            # Actualizar state.analisis (campo dinámico requerido por la tarea)
            object.__setattr__(state, "analisis", analisis_json)
            
            # Sincronizar con el campo oficial de SharedState
            state.analisis_conductual = json.dumps(analisis_json, ensure_ascii=False)
            
            logger.info(f"📊 Análisis conductual completado para el alumno {state.alumno_id}.")
            return state

        except Exception as e:
            logger.error(f"❌ Error en AnalistaAgent.analyze: {e}", exc_info=True)
            return state
