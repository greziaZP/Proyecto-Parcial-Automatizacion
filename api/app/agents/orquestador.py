from app.state.shared_state import SharedState
from app.agents.analista import AnalistaAgent
from app.agents.evaluador import EvaluadorAgent
from app.agents.mediador import MediadorAgent

class OrquestadorAgent:

    @staticmethod
    def _determinar_siguiente_agente(state: SharedState) -> str:
        if not state.analisis_conductual:
            return "Analista"
        if not state.resultado_rag_reglamento:
            return "Evaluador"
        if not state.dictamen_final:
            return "Mediador"
        return "Finalizar"
    

    def ejecutar(self, state: SharedState, mensaje: str = None) -> SharedState:
        while True:
            target_agent = self._determinar_siguiente_agente(state)
            print(f"\n[ORQUESTADOR] Estado → analisis={bool(state.analisis_conductual)}, "
                  f"rag={bool(state.resultado_rag_reglamento)}, dictamen={bool(state.dictamen_final)}")
            print(f"[ORQUESTADOR] Routing determinístico → {target_agent}")

            state.estado_actual = target_agent

            if target_agent == "Finalizar":
                break
            elif target_agent == "Analista":
                print("==> Transfiriendo a Agente Analista...")
                state = AnalistaAgent().ejecutar(state)
            elif target_agent == "Evaluador":
                print("==> Transfiriendo a Agente Evaluador...")
                state = EvaluadorAgent().ejecutar(state, mensaje)
            elif target_agent == "Mediador":
                print("==> Transfiriendo a Agente Mediador...")
                state = MediadorAgent().ejecutar(state, mensaje)

        return state