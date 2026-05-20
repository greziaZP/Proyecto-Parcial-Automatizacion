"""
UI: Asistencia Biométrica — Streamlit
======================================
Dos pestañas:
  1. Enrolamiento → Seleccionar estudiante + capturar rostro
  2. Ingreso (Puerta) → Capturar foto → reconocimiento automático (máx. 5 intentos)
"""

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def _safe_json(response: requests.Response) -> dict | None:
    try:
        return response.json()
    except ValueError:
        return None

# ─── Configuración de la página ──────────────────────────────────────────────
st.set_page_config(
    page_title="Sistema de Asistencia Biométrica",
    page_icon="🏫",
    layout="wide",
)

# ─── Estilos personalizados ──────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght@100..700&display=swap');

    :root {
        --bg: #f8f9ff;
        --surface: #ffffff;
        --surface-2: #e5eeff;
        --surface-3: #dce9ff;
        --text: #0b1c30;
        --muted: #424656;
        --primary: #0050cb;
        --secondary: #00ccf9;
        --outline: #c2c6d8;
        --inverse: #213145;
        --success: #22c55e;
        --warning: #f59e0b;
        --danger: #ef4444;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background: var(--bg);
        color: var(--text);
    }

    .app-shell {
        max-width: 1400px;
        margin: 0 auto;
        padding: 16px 20px 28px;
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 18px;
        background: #f3f6ff;
        border: 1px solid rgba(0, 0, 0, 0.04);
        border-radius: 16px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
        position: sticky;
        top: 0;
        z-index: 2;
        backdrop-filter: blur(12px);
    }

    .nav-links {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .nav-link {
        text-decoration: none;
        color: var(--muted);
        padding: 6px 14px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        background: transparent;
        transition: background 0.2s ease, color 0.2s ease;
    }

    .nav-link.active {
        background: #e6edff;
        color: var(--primary);
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: var(--primary);
    }

    .brand .material-symbols-outlined {
        font-variation-settings: 'FILL' 1;
    }

    .badge-live {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        border-radius: 999px;
        background: var(--surface-2);
        border: 1px solid var(--outline);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--primary);
    }

    .panel {
        background: var(--surface);
        border: 1px solid var(--outline);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05);
    }

    .history-panel {
        background: var(--surface);
        border: 1px solid var(--outline);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05);
        position: sticky;
        top: 92px;
    }

    .history-title {
        font-size: 18px;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 12px;
    }

    .history-item {
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        padding: 10px 0;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .history-item:last-child {
        border-bottom: none;
    }

    .history-name {
        font-weight: 600;
        color: var(--text);
    }

    .history-meta {
        font-size: 12px;
        color: var(--muted);
    }

    .section-title {
        font-size: 28px;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 6px;
    }

    .section-subtitle {
        color: var(--muted);
        font-size: 15px;
    }

    .helper-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 14px;
    }

    .helper-card {
        background: var(--surface-2);
        border-radius: 12px;
        padding: 12px;
        border: 1px solid rgba(0, 0, 0, 0.04);
        display: flex;
        gap: 10px;
        align-items: flex-start;
    }

    .helper-card .material-symbols-outlined {
        color: var(--primary);
        font-variation-settings: 'FILL' 1;
    }


    .scan-line {
        position: absolute;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--secondary), transparent);
        animation: scan 2.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
        box-shadow: 0 0 10px rgba(0, 209, 255, 0.8);
    }

    @keyframes scan {
        0% { top: 10%; opacity: 0; }
        10% { opacity: 1; }
        90% { opacity: 1; }
        100% { top: 90%; opacity: 0; }
    }

    .result-card {
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        margin-top: 10px;
        animation: fadeIn 0.4s ease;
    }

    .result-success {
        background: linear-gradient(135deg, #052e16, #14532d);
        border: 1px solid var(--success);
        color: #ffffff;
    }

    .result-error {
        background: linear-gradient(135deg, #450a0a, #7f1d1d);
        border: 1px solid var(--danger);
        color: #ffffff;
    }

    .badge-pill {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 999px;
        font-weight: 600;
        font-size: 13px;
        margin-top: 8px;
    }

    .badge-success { background: var(--success); color: #052e16; }
    .badge-warning { background: var(--warning); color: #451a03; }

    .attempts {
        display: flex;
        justify-content: center;
        gap: 6px;
        margin: 12px 0;
    }

    .attempts .dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #334155;
    }

    .attempts .dot.used { background: var(--danger); }

    div[data-testid="stCameraInput"] > label,
    div[data-testid="stSelectbox"] > label {
        font-weight: 600;
    }

    div[data-testid="stCameraInput"] {
        background: transparent;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
""", unsafe_allow_html=True)

# ─── Estado de sesión ────────────────────────────────────────────────────────
if "intentos_ingreso" not in st.session_state:
    st.session_state.intentos_ingreso = 0
if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado = None
if "foto_anterior_ingreso" not in st.session_state:
    st.session_state.foto_anterior_ingreso = None
if "historial_asistencia" not in st.session_state:
    st.session_state.historial_asistencia = []
if "historial_key" not in st.session_state:
    st.session_state.historial_key = None

MAX_INTENTOS = 5

query = st.query_params if hasattr(st, "query_params") else {}
raw_tab = query.get("tab", "ingreso") if hasattr(query, "get") else "ingreso"
if isinstance(raw_tab, list):
    active_tab = raw_tab[0] if raw_tab else "ingreso"
else:
    active_tab = raw_tab
active_tab = active_tab if active_tab in {"ingreso", "registro"} else "ingreso"

nav_ingreso = "nav-link active" if active_tab == "ingreso" else "nav-link"
nav_registro = "nav-link active" if active_tab == "registro" else "nav-link"

st.markdown(
    f"""
    <div class="app-shell">
        <div class="topbar">
            <div class="brand">
                <span class="material-symbols-outlined">fingerprint</span>
                <span>COLEGIO NARVAES</span>
            </div>
            <div class="nav-links">
                <a class="{nav_ingreso}" href="?tab=ingreso" target="_self">Escanear</a>
                <a class="{nav_registro}" href="?tab=registro" target="_self">Registrar</a>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Enrolamiento de rostros
# ─────────────────────────────────────────────────────────────────────────────

if active_tab == "registro":
    st.markdown("<div class=\"app-shell\">", unsafe_allow_html=True)
    left, right = st.columns([5, 7], gap="large")

    with left:
        st.markdown(
            """
            <div class="panel">
                <div class="section-title">Nuevo Registro</div>
                <div class="section-subtitle">
                    Seleccione un estudiante y capture su foto frontal para enrolarlo.
                </div>
                <div class="helper-grid">
                    <div class="helper-card">
                        <span class="material-symbols-outlined">eyeglasses</span>
                        <div>
                            <strong>Retire anteojos</strong><br>
                            Evite accesorios que cubran el rostro.
                        </div>
                    </div>
                    <div class="helper-card">
                        <span class="material-symbols-outlined">face</span>
                        <div>
                            <strong>Mire al frente</strong><br>
                            Alinee su rostro al centro de la camara.
                        </div>
                    </div>
                    <div class="helper-card">
                        <span class="material-symbols-outlined">lightbulb</span>
                        <div>
                            <strong>Buena iluminacion</strong><br>
                            Sin sombras pronunciadas.
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Obtener lista de estudiantes sin rostro
    try:
        resp = requests.get(f"{API_BASE}/biometria/estudiantes_sin_rostro", timeout=10)
        resp.raise_for_status()
        estudiantes = resp.json()
    except requests.RequestException as e:
        st.error(f"No se pudo conectar con el backend: {e}")
        estudiantes = []

    with right:
        st.markdown(
            """
            <div class="panel">
                <div class="section-title">Captura biometrica</div>
                <div class="section-subtitle">Use la camara para registrar el rostro.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not estudiantes:
            st.info("Todos los estudiantes ya tienen rostro registrado o no hay datos.")
        else:
            opciones = {
                f"{est['nombres']} {est['apellidos']}": est["uid"]
                for est in estudiantes
            }

            seleccion = st.selectbox(
                "Seleccione un estudiante",
                options=list(opciones.keys()),
                placeholder="Elija un estudiante…",
            )

            foto = st.camera_input("Camara de registro", key="registro_cam")

            if st.button("Registrar rostro", type="primary", use_container_width=True):
                if not seleccion:
                    st.warning("Seleccione un estudiante antes de registrar.")
                elif not foto:
                    st.warning("Debe capturar una foto antes de registrar.")
                else:
                    estudiante_uid = opciones[seleccion]

                    with st.spinner("Enviando rostro a AWS Rekognition…"):
                        try:
                            files = {"archivo": ("rostro.jpg", foto.getvalue(), "image/jpeg")}
                            data = {"estudiante_uid": estudiante_uid}
                            resp = requests.post(
                                f"{API_BASE}/biometria/registrar_rostro",
                                files=files,
                                data=data,
                                timeout=30,
                            )

                            data = _safe_json(resp)

                            if resp.status_code == 201:
                                mensaje = (data or {}).get("mensaje", "Registro exitoso.")
                                st.success(mensaje)
                                st.balloons()
                            else:
                                detalle = (data or {}).get("detail") or resp.text or "Error inesperado."
                                st.error(f"Error: {detalle}")

                        except requests.RequestException as e:
                            st.error(f"Error de conexion: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Ingreso por puerta principal
# ─────────────────────────────────────────────────────────────────────────────

if active_tab == "ingreso":
    st.markdown("<div class=\"app-shell\">", unsafe_allow_html=True)
    main_col, history_col = st.columns([3, 1], gap="large")

    with main_col:
        st.markdown(
            """
            <div class="panel">
                <div class="section-title">Ingreso por puerta principal</div>
                <div class="section-subtitle">Capture la foto y el sistema identificara al estudiante.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Mostrar resultado previo si existe ────────────────────────────────
        resultado = st.session_state.ultimo_resultado

        if resultado and resultado.get("tipo") == "fallo":
            st.markdown(
                f"""
                <div class="result-card result-error">
                    <div style="font-size:36px;">❌</div>
                    <div style="font-size:20px; font-weight:700;">No se pudo identificar al estudiante</div>
                    <div style="opacity:0.9; margin-top:6px;">
                        Se agotaron los {MAX_INTENTOS} intentos de reconocimiento.<br>
                        Verifique que el estudiante este enrolado en el sistema.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Barra de intentos ────────────────────────────────────────────────
        intentos = st.session_state.intentos_ingreso
        if intentos > 0 and (not resultado or resultado.get("tipo") != "exito"):
            dots = ""
            for i in range(MAX_INTENTOS):
                clase = "used" if i < intentos else ""
                dots += f'<div class="dot {clase}"></div>'
            st.markdown(
                f"""
                <div class="attempts">{dots}</div>
                <p style="text-align:center; color:#424656; font-size:13px;">
                    Intento {intentos} de {MAX_INTENTOS}
                </p>
                """,
                unsafe_allow_html=True,
            )

        # ── Controles de cámara ──────────────────────────────────────────────
        bloqueado = intentos >= MAX_INTENTOS

        if bloqueado:
            if st.button("🔄 Reintentar (resetear intentos)", type="primary", use_container_width=True):
                st.session_state.intentos_ingreso = 0
                st.session_state.ultimo_resultado = None
                st.session_state.foto_anterior_ingreso = None
                st.rerun()
        else:
            foto_puerta = st.camera_input("Camara de la puerta principal", key="ingreso_cam")

            # Envío automático al capturar foto (sin botón)
            if foto_puerta is not None:
                foto_bytes = foto_puerta.getvalue()

                # Solo enviar si es una foto nueva (evitar reenvío en reruns)
                if foto_bytes != st.session_state.foto_anterior_ingreso:
                    st.session_state.foto_anterior_ingreso = foto_bytes

                    with st.spinner("🔍 Identificando estudiante…"):
                        try:
                            files = {"archivo": ("puerta.jpg", foto_bytes, "image/jpeg")}
                            resp = requests.post(
                                f"{API_BASE}/biometria/marcar_ingreso",
                                files=files,
                                timeout=30,
                            )

                            data = _safe_json(resp)

                            if resp.status_code == 200 and data:
                                key = f"{data.get('estudiante_uid')}-{data.get('hora_llegada')}"
                                if key and key != st.session_state.historial_key:
                                    st.session_state.historial_key = key
                                    st.session_state.historial_asistencia.insert(0, {
                                        "nombres": data.get("nombres", ""),
                                        "apellidos": data.get("apellidos", ""),
                                        "uid": data.get("estudiante_uid", ""),
                                        "hora": data.get("hora_llegada", ""),
                                    })
                                    st.session_state.historial_asistencia = st.session_state.historial_asistencia[:20]

                                st.session_state.intentos_ingreso = 0
                                st.session_state.ultimo_resultado = None
                                st.rerun()
                            else:
                                st.session_state.intentos_ingreso += 1
                                detalle = (data or {}).get("detail") or resp.text or "Error inesperado."

                                if st.session_state.intentos_ingreso >= MAX_INTENTOS:
                                    st.session_state.ultimo_resultado = {"tipo": "fallo"}
                                    st.rerun()
                                else:
                                    st.warning(
                                        f"Intento {st.session_state.intentos_ingreso}/{MAX_INTENTOS} "
                                        f"— {detalle}. Vuelva a capturar la foto."
                                    )

                        except requests.RequestException as e:
                            st.session_state.intentos_ingreso += 1

                            if st.session_state.intentos_ingreso >= MAX_INTENTOS:
                                st.session_state.ultimo_resultado = {"tipo": "fallo"}
                                st.rerun()
                            else:
                                st.error(
                                    f"Intento {st.session_state.intentos_ingreso}/{MAX_INTENTOS} "
                                    f"— Error de conexion: {e}"
                                )

    with history_col:
        items = st.session_state.historial_asistencia
        if items:
            rows = "".join(
                f"<div class=\"history-item\">"
                f"<div class=\"history-name\">{item["nombres"]} {item["apellidos"]}</div>"
                f"<div class=\"history-meta\">"
                f"{"ID: " + item["uid"] if item["uid"] else ""}{" · " if item["uid"] else ""}Hora: {item["hora"]}"
                f"</div>"
                f"</div>"
                for item in items
            )
        else:
            rows = "<div class=\"history-meta\">Sin registros aún.</div>"

        st.markdown(
            f"<div class=\"history-panel\">"
            f"<div class=\"history-title\">Historial del dia</div>"
            f"{rows}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
