import os
import json
import logging
import sys
from pathlib import Path
from app.state.shared_state import SharedState
import anthropic

# Asegurar que la raíz del proyecto está en sys.path para poder importar vector
_root_dir = str(Path(__file__).parent.parent.parent.parent)
if _root_dir not in sys.path:
    sys.path.append(_root_dir)

from vector.vector_tools import consultar_reglamento

logger = logging.getLogger("EvaluadorAgent")

class EvaluadorAgent:
    def __init__(self):
        self.system_prompt = """
        Eres el Agente Evaluador Normativo, experto en RAG y reglamentos del 
        Colegio Rafael Narváez Cadenillas.
        
        Alcance:
        1. Recibirás en el SharedState el contexto de la incidencia y quizás el
           'analisis_conductual' previo.
        2. Tu misión es contrastar esta situación con las normas institucionales.
        3. DEBES invocar OBLIGATORIAMENTE la herramienta MCP 'consultar_reglamento'
           (Base de Datos Vectorial) usando los términos clave del problema (ej."falta médica", 
           "suspensión").
        4. Consolida la normativa aplicable extraida y determina si el caso en cuestión
           es sancionable, perdonable o si requiere derivación al psicólogo institucional.
        5. Escribe un resumen de tu evaluación en 'resultado_rag_reglamento' dentro 
           del SharedState.
        6. Devuelve el control al Agente Orquestador.
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

    def evaluate(self, state: SharedState) -> SharedState:
        """
        Consulta reglamento vía Vector DB, analiza normativas y guarda en 'evaluacion'
        y 'resultado_rag_reglamento'.
        """
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("❌ ANTHROPIC_API_KEY no configurada.")
                return state

            client = anthropic.Anthropic(api_key=api_key)

            # Obtener datos de entrada para la evaluación
            analisis = getattr(state, "analisis", None)
            if not analisis:
                # Fallback al campo oficial de SharedState
                analisis = state.analisis_conductual or "Sin análisis conductual previo."

            justificacion = getattr(state, "justificacion", None) or "justificación médica por emergencia familiar"

            # 1. Definir la herramienta consultar_reglamento
            schema_consultar_reglamento = {
                "name": "consultar_reglamento",
                "description": (
                    "Realiza una búsqueda semántica (RAG) en la Base de Datos Vectorial "
                    "sobre el reglamento y normas del Colegio Rafael Narváez Cadenillas."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Términos de búsqueda clave del problema (ej. 'falta médica', 'plazo justificación')."
                        }
                    },
                    "required": ["query"]
                }
            }

            user_message = (
                f"Análisis conductual previo:\n{json.dumps(analisis, indent=2, default=str)}\n\n"
                f"Justificación presentada:\n{justificacion}\n\n"
                f"Por favor, invoca OBLIGATORIAMENTE la herramienta 'consultar_reglamento' "
                f"para buscar las normas aplicables a este caso."
            )

            # Primera llamada a la API
            logger.info("📞 EvaluadorAgent realizando primera llamada a Claude con herramientas...")
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ],
                tools=[schema_consultar_reglamento]
            )

            # Verificar si Claude solicitó el uso de la herramienta
            tool_use_block = None
            for content in response.content:
                if content.type == "tool_use":
                    tool_use_block = content
                    break

            if tool_use_block:
                tool_use_id = tool_use_block.id
                tool_name = tool_use_block.name
                tool_input = tool_use_block.input
                logger.info(f"🛠️ Claude solicitó usar la herramienta '{tool_name}' con input: {tool_input}")

                # Ejecutar la herramienta en Qdrant
                try:
                    tool_result = consultar_reglamento(query=tool_input["query"], top_k=3)
                except Exception as e:
                    logger.error(f"❌ Error al ejecutar herramienta consultar_reglamento: {e}")
                    tool_result = []

                # Segunda llamada a la API con el resultado de la herramienta
                logger.info("📞 EvaluadorAgent realizando segunda llamada a Claude con el resultado RAG...")
                final_user_prompt = (
                    "Ahora que tienes las normas del reglamento recuperadas, decide sobre la justificación. "
                    "Responde ÚNICAMENTE con un JSON válido con estas claves:\n"
                    "- 'decision': string ('aprobado', 'rechazado' o 'pendiente')\n"
                    "- 'articulos_aplicados': lista de strings (ej. ['Art. 1', 'Art. 2'])\n"
                    "- 'razon': string (explicación legal/normativa detallada)\n"
                    "No agregues texto introductorio ni explicaciones fuera del JSON."
                )

                response_final = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    system=self.system_prompt,
                    messages=[
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": response.content},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": json.dumps(tool_result, ensure_ascii=False)
                                },
                                {
                                    "type": "text",
                                    "text": final_user_prompt
                                }
                            ]
                        }
                    ],
                    tools=[schema_consultar_reglamento]
                )

                response_text = response_final.content[0].text.strip()
            else:
                logger.warning("⚠️ Claude no invocó la herramienta. Procesando de forma directa.")
                response_text = response.content[0].text.strip()

            evaluacion_json = self._parse_json(response_text)

            # Actualizar state.evaluacion (campo dinámico)
            object.__setattr__(state, "evaluacion", evaluacion_json)
            
            # Sincronizar con el campo oficial de SharedState
            state.resultado_rag_reglamento = json.dumps(evaluacion_json, ensure_ascii=False)

            logger.info(f"⚖️ Evaluación normativa completada para el alumno {state.alumno_id}.")
            return state

        except Exception as e:
            logger.error(f"❌ Error en EvaluadorAgent.evaluate: {e}", exc_info=True)
            return state
