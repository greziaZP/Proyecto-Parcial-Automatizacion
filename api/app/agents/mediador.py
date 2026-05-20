import os
import json
import logging
from app.state.shared_state import SharedState
import anthropic

logger = logging.getLogger("MediadorAgent")

class MediadorAgent:
    def __init__(self):
        self.system_prompt = """
        Eres el Agente Mediador (Resolutor de Conflictos). Tu tarea es emitir una
        decisión o acción final combinando la historia del alumno y las normas del colegio.
        
        Alcance:
        1. Serás convocado cuando el 'analisis_conductual' y el 'resultado_rag_reglamento'
           ya estén documentados en el SharedState.
        2. Tienes que leer ambas variables y redactar un fallo oficial.
        3. Tu respuesta puede ser: "Falta Justificada Aceptada", "Rechazada por falta de evidencia",
           o "Requiere citación con apoderado".
        4. NO debes invocar herramientas de base de datos de lectura.
        5. Si determinas que se necesita una citación, indícalo expresamente para que el 
           Orquestador ejecute la herramienta de MCP correspondiente.
        6. Guarda tu resolución final en la variable 'dictamen_final' del SharedState.
        7. Devuelve el control al Agente Orquestador.
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

    def mediate(self, state: SharedState) -> SharedState:
        """
        Genera los mensajes finales para el padre y la administración basándose en el caso.
        """
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("❌ ANTHROPIC_API_KEY no configurada.")
                return state

            client = anthropic.Anthropic(api_key=api_key)

            # Obtener datos acumulados
            evaluacion = getattr(state, "evaluacion", None)
            if not evaluacion:
                # Fallback al campo oficial
                evaluacion = state.resultado_rag_reglamento or "Sin evaluación de reglamento."

            analisis = getattr(state, "analisis", None)
            if not analisis:
                # Fallback al campo oficial
                analisis = state.analisis_conductual or "Sin análisis conductual."

            user_message = (
                f"Evaluación del reglamento:\n{json.dumps(evaluacion, indent=2, default=str)}\n\n"
                f"Análisis conductual previo:\n{json.dumps(analisis, indent=2, default=str)}\n\n"
                f"Por favor genera un dictamen final. Responde ÚNICAMENTE con un JSON válido con estas claves:\n"
                f"- 'mensaje_padre': string (mensaje en español dirigido al padre/apoderado con un tono muy empático)\n"
                f"- 'nota_admin': string (nota interna formal dirigida a la administración escolar)\n"
                f"No agregues texto fuera del JSON."
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
            mensaje_final_json = self._parse_json(response_text)

            # Actualizar state.mensaje_final (campo dinámico)
            object.__setattr__(state, "mensaje_final", mensaje_final_json)
            
            # Sincronizar con el campo oficial de SharedState
            state.dictamen_final = json.dumps(mensaje_final_json, ensure_ascii=False)

            logger.info(f"🤝 Mediación final completada para el alumno {state.alumno_id}.")
            return state

        except Exception as e:
            logger.error(f"❌ Error en MediadorAgent.mediate: {e}", exc_info=True)
            return state

    def resolve(self, state: SharedState) -> SharedState:
        """Punto de entrada compatible con la versión anterior."""
        return self.mediate(state)
