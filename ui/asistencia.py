"""
ui/asistencia.py — Toma de asistencia con renderizado server-side.

El servidor consulta la API, obtiene secciones/horarios/alumnos y
entrega el HTML ya poblado. El JS solo maneja la cámara y el polling.
"""
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()
API_BASE = "http://localhost:8000"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de consulta a la API
# ──────────────────────────────────────────────────────────────────────────────

def _get(ruta: str) -> list | dict | None:
    try:
        with httpx.Client(timeout=4.0) as c:
            r = c.get(f"{API_BASE}{ruta}")
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def _hora_actual() -> str:
    return datetime.now().strftime("%H:%M")


def _estado_clase(hora_ini: str, hora_fin: str) -> str:
    ahora = _hora_actual()
    if hora_ini <= ahora <= hora_fin:
        return "activa"
    if hora_fin < ahora:
        return "finalizada"
    return "pendiente"


# ──────────────────────────────────────────────────────────────────────────────
# Generadores de fragmentos HTML
# ──────────────────────────────────────────────────────────────────────────────

_BADGE_ESTADO = {
    "presente":     ("bg-green-100 text-green-800",   "Presente"),
    "tardanza":     ("bg-yellow-100 text-yellow-800", "Tardanza"),
    "falta":        ("bg-red-100 text-red-800",       "Falta"),
    "justificada":  ("bg-blue-100 text-blue-800",     "Justificada"),
    "sin_registro": ("bg-gray-100 text-gray-600",     "Pendiente"),
}


def _html_opciones_secciones(secciones: list, seleccionada: str) -> str:
    opts = '<option value="">— Selecciona una sección —</option>'
    for s in secciones:
        sel = 'selected' if s["uid"] == seleccionada else ''
        opts += f'<option value="{s["uid"]}" {sel}>{s["label"]}</option>'
    return opts


def _html_opciones_horarios(horarios: list, seleccionado: str) -> str:
    if not horarios:
        return '<option value="">Sin horarios para hoy</option>'
    opts = '<option value="">— Selecciona un horario —</option>'
    for h in horarios:
        estado = _estado_clase(h["hora_inicio"], h["hora_fin"])
        sufijo = " ✓" if estado == "activa" else " (finalizada)" if estado == "finalizada" else ""
        sel    = 'selected' if h["uid"] == seleccionado else ''
        opts  += f'<option value="{h["uid"]}" {sel}>{h["hora_inicio"]} – {h["hora_fin"]} · {h["curso_nombre"]}{sufijo}</option>'
    return opts


def _html_tarjeta_alumno(alumno: dict, horario_uid: str) -> str:
    estado    = alumno.get("estado_asistencia") or "sin_registro"
    cls_badge, texto_badge = _BADGE_ESTADO.get(estado, _BADGE_ESTADO["sin_registro"])
    iniciales = (alumno.get("nombres", "?")[:1] + alumno.get("apellidos", "?")[:1]).upper()

    boton_marcar = ""
    if estado == "sin_registro" and horario_uid:
        est_uid  = alumno["estudiante_uid"]
        mat_uid  = alumno["matricula_uid"]
        boton_marcar = f"""
        <button onclick="marcarPresente('{est_uid}','{mat_uid}','{horario_uid}',this)"
                class="text-xs text-primary hover:underline font-semibold mt-1">
            Marcar ✓
        </button>"""

    return f"""
    <div id="alumno-{alumno['estudiante_uid']}"
         class="flex items-center gap-3 p-3 bg-white rounded-xl border border-outline-variant shadow-sm">
        <div class="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold shrink-0">
            {iniciales}
        </div>
        <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-on-surface truncate">{alumno['nombre_completo']}</p>
            <p class="text-xs text-on-surface-variant">DNI: {alumno['dni_estudiante']} · {alumno['seccion_label']}</p>
        </div>
        <div class="flex flex-col items-end shrink-0">
            <span class="text-xs font-semibold px-2 py-0.5 rounded-full {cls_badge}">{texto_badge}</span>
            {boton_marcar}
        </div>
    </div>"""


def _html_info_horario(horario: dict) -> str:
    if not horario:
        return ""
    estado = _estado_clase(horario["hora_inicio"], horario["hora_fin"])
    color  = "bg-green-50 border-green-200 text-green-800" if estado == "activa" else "bg-surface-container border-outline-variant text-on-surface-variant"
    return f"""
    <div class="p-3 rounded-xl border {color} text-sm mb-3">
        <p class="font-bold">{horario['curso_nombre']}</p>
        <p class="text-xs mt-0.5">{horario['hora_inicio']} – {horario['hora_fin']} · Doc: {horario['docente_nombre']}</p>
        <p class="text-xs mt-0.5 font-semibold">{"🟢 En curso ahora" if estado == "activa" else "⏳ Pendiente" if estado == "pendiente" else "✅ Finalizada"}</p>
    </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Estilos y config compartida
# ──────────────────────────────────────────────────────────────────────────────

_HEAD = """
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
<script>
    tailwind.config = { theme: { extend: { colors: {
        "primary":"#002068","on-primary":"#ffffff","primary-container":"#003399",
        "secondary":"#00668a","on-secondary":"#ffffff",
        "error":"#ba1a1a","on-error":"#ffffff","error-container":"#ffdad6",
        "background":"#f8f9ff","on-background":"#0b1c30","surface":"#f8f9ff",
        "on-surface":"#0b1c30","on-surface-variant":"#444653",
        "surface-container-lowest":"#ffffff","surface-container":"#e5eeff",
        "surface-container-high":"#dce9ff","outline":"#747684","outline-variant":"#c4c5d5",
    }}}}
</script>
<style>
    body { font-family:'Manrope',sans-serif; }
    .material-symbols-outlined { font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24; }
    .material-symbols-outlined.fill { font-variation-settings:'FILL' 1; }
    @keyframes scan { 0%{top:5%;opacity:0} 10%{opacity:1} 90%{opacity:1} 100%{top:95%;opacity:0} }
    .animate-scan { animation: scan 3s cubic-bezier(.4,0,.2,1) infinite; }
    @keyframes pulso { 0%,100%{border-color:rgba(0,51,153,.3)} 50%{border-color:rgba(0,51,153,1);box-shadow:0 0 12px rgba(0,51,153,.4)} }
    .esquina { position:absolute;width:36px;height:36px;border-color:#fff;border-style:solid;animation:pulso 2s infinite; }
    @keyframes slideIn { from{transform:translateX(16px);opacity:0} to{transform:translateX(0);opacity:1} }
    .slide-in { animation:slideIn .3s ease-out forwards; }
</style>
"""

_SIDEBAR = """
<aside class="h-screen w-60 fixed left-0 top-0 flex flex-col bg-white shadow-lg z-50 py-8 border-r border-outline-variant">
    <div class="px-5 mb-6 flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-primary flex items-center justify-center text-white font-bold">N</div>
        <div>
            <p class="font-bold text-primary text-sm">Narváez</p>
            <p class="text-xs text-on-surface-variant">Asistencia Biométrica</p>
        </div>
    </div>
    <nav class="px-3 space-y-1 mb-4">
        <a href="/" class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-on-surface-variant hover:bg-surface-container hover:text-primary transition-colors text-sm">
            <span class="material-symbols-outlined text-xl">dashboard</span> Dashboard
        </a>
        <a href="/asistencia" class="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-primary/10 text-primary font-semibold text-sm">
            <span class="material-symbols-outlined text-xl fill">face</span> Tomar Asistencia
        </a>
    </nav>
</aside>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Ensamblado de la página completa
# ──────────────────────────────────────────────────────────────────────────────

def _renderizar(
    secciones: list,
    horarios: list,
    alumnos: list,
    horario_actual: Optional[dict],
    seccion_uid: str,
    horario_uid: str,
    error: Optional[str],
) -> str:

    html_secciones = _html_opciones_secciones(secciones, seccion_uid)
    html_horarios  = _html_opciones_horarios(horarios, horario_uid)
    html_info      = _html_info_horario(horario_actual) if horario_actual else ""
    html_alumnos   = (
        "".join(_html_tarjeta_alumno(a, horario_uid) for a in alumnos)
        if alumnos
        else '<p class="text-xs text-on-surface-variant text-center py-6">Selecciona una sección y horario.</p>'
    )

    presentes    = sum(1 for a in alumnos if a.get("estado_asistencia") in ("presente", "tardanza"))
    total_alumnos = len(alumnos)
    subtitulo     = f"Sesión: {horario_actual['curso_nombre']} · {horario_actual['hora_inicio']}–{horario_actual['hora_fin']}" if horario_actual else "Selecciona sección y horario para comenzar"
    banner_error  = f'<div class="mb-4 p-3 bg-error-container text-on-error-container rounded-xl text-sm">{error}</div>' if error else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <title>Toma de Asistencia — Narváez</title>
    <meta name="description" content="Registra la asistencia de los alumnos mediante reconocimiento facial. Selecciona la sección y el horario para iniciar."/>
    {_HEAD}
</head>
<body class="bg-background text-on-background min-h-screen overflow-hidden flex">

{_SIDEBAR}

<div class="flex-1 flex flex-col ml-60 min-h-screen">

    <!-- Barra superior -->
    <header class="h-14 bg-white border-b border-outline-variant flex justify-between items-center px-6 sticky top-0 z-40">
        <div class="flex items-center gap-2 text-on-surface-variant">
            <span class="material-symbols-outlined text-base">videocam</span>
            <span class="text-xs font-semibold uppercase tracking-wider">Sesión Activa</span>
            <span class="ml-2 text-xs text-on-surface-variant" id="subtitulo-top">{subtitulo}</span>
        </div>
        <div class="flex items-center gap-3">
            <div class="text-xs bg-surface-container px-3 py-1 rounded-lg text-on-surface-variant">
                Registrados hoy: <span id="contador" class="font-bold text-primary">{presentes}</span>
                / <span class="font-bold">{total_alumnos}</span>
            </div>
            <button onclick="finalizarSesion()"
                    class="bg-error text-white px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1 hover:opacity-90 transition-opacity">
                <span class="material-symbols-outlined text-base">stop_circle</span>
                Finalizar Sesión
            </button>
        </div>
    </header>

    <main class="flex-1 p-6 grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-56px)] overflow-hidden">

        <!-- Cámara (2 cols) -->
        <section class="lg:col-span-2 bg-black rounded-2xl overflow-hidden relative shadow-lg flex flex-col border border-outline">

            <!-- Feed de video -->
            <video id="camara" autoplay playsinline muted class="absolute inset-0 w-full h-full object-cover opacity-70"></video>
            <div id="sin-camara" class="absolute inset-0 flex items-center justify-center text-white/40">
                <div class="text-center">
                    <span class="material-symbols-outlined text-6xl">videocam_off</span>
                    <p class="text-sm mt-2">Cámara no disponible</p>
                </div>
            </div>

            <!-- Info superior -->
            <div class="absolute top-0 left-0 w-full p-4 flex justify-between items-center z-20 bg-gradient-to-b from-black/60 to-transparent">
                <div class="flex items-center gap-2 bg-black/40 px-3 py-1 rounded-lg backdrop-blur-sm">
                    <span class="relative flex h-2.5 w-2.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                        <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500"></span>
                    </span>
                    <span class="text-white text-xs font-semibold">EN VIVO</span>
                </div>
                <div class="bg-black/40 px-3 py-1 rounded-lg backdrop-blur-sm text-white text-xs font-semibold" id="etiqueta-sesion">
                    {subtitulo if horario_actual else "Sin sesión activa"}
                </div>
            </div>

            <!-- Visor de escaneo -->
            <div class="relative flex-1 flex items-center justify-center z-10">
                <div class="relative w-64 h-80">
                    <div class="esquina top-0 left-0 border-t-4 border-l-4 rounded-tl-lg"></div>
                    <div class="esquina top-0 right-0 border-t-4 border-r-4 rounded-tr-lg"></div>
                    <div class="esquina bottom-0 left-0 border-b-4 border-l-4 rounded-bl-lg"></div>
                    <div class="esquina bottom-0 right-0 border-b-4 border-r-4 rounded-br-lg"></div>
                    <div class="absolute left-0 w-full h-0.5 bg-primary/80 shadow-[0_0_10px_rgba(0,51,153,.8)] animate-scan"></div>
                </div>
            </div>

            <!-- Estado inferior -->
            <div class="relative z-20 bg-white/90 backdrop-blur-md border-t border-outline-variant px-4 py-3 flex items-center justify-center gap-2">
                <span class="material-symbols-outlined text-primary animate-pulse">face</span>
                <span class="text-sm font-medium text-on-surface" id="estado-escaneo">Buscando rostros…</span>
            </div>
        </section>

        <!-- Panel derecho -->
        <section class="lg:col-span-1 flex flex-col gap-3 overflow-hidden">

            <!-- Selector de sesión -->
            <div class="bg-white rounded-2xl p-4 border border-outline-variant shadow-sm shrink-0">
                <h3 class="text-sm font-bold text-on-background mb-3 flex items-center gap-2">
                    <span class="material-symbols-outlined text-primary text-lg">tune</span>
                    Seleccionar Sesión
                </h3>
                {banner_error}
                <form method="GET" action="/asistencia" class="space-y-2">
                    <div>
                        <label class="text-xs text-on-surface-variant font-semibold block mb-1">Sección</label>
                        <select name="seccion_uid" id="sel-seccion"
                                onchange="this.form.submit()"
                                class="w-full text-sm border border-outline-variant rounded-lg px-3 py-2 bg-surface-container focus:outline-none focus:border-primary">
                            {html_secciones}
                        </select>
                    </div>
                    <div>
                        <label class="text-xs text-on-surface-variant font-semibold block mb-1">Horario</label>
                        <select name="horario_uid" id="sel-horario"
                                onchange="this.form.submit()"
                                {'disabled' if not seccion_uid else ''}
                                class="w-full text-sm border border-outline-variant rounded-lg px-3 py-2 bg-surface-container focus:outline-none focus:border-primary">
                            {html_horarios}
                        </select>
                    </div>
                </form>
                {html_info}
            </div>

            <!-- Lista de alumnos -->
            <div class="bg-white rounded-2xl border border-outline-variant shadow-sm flex flex-col flex-1 overflow-hidden">
                <div class="p-4 border-b border-outline-variant flex justify-between items-center shrink-0">
                    <h3 class="text-sm font-bold text-on-background">
                        Alumnos
                        {f'<span class="text-primary">({total_alumnos})</span>' if total_alumnos else ""}
                    </h3>
                    <span class="text-xs text-on-surface-variant">
                        {f'{presentes} registrados' if total_alumnos else ''}
                    </span>
                </div>
                <div id="lista-alumnos" class="flex-1 overflow-y-auto p-3 space-y-2">
                    {html_alumnos}
                </div>
            </div>

        </section>
    </main>
</div>

<script>
const API       = "{API_BASE}";
const HORARIO   = "{horario_uid}";
const SECCION   = "{seccion_uid}";
let   marcados  = new Set([{",".join(f'"{a["estudiante_uid"]}"' for a in alumnos if a.get("estado_asistencia") and a["estado_asistencia"] != "sin_registro")}]);
let   intervalId = null;

// ── Cámara ──────────────────────────────────────────────────────────────
async function iniciarCamara() {{
    try {{
        const stream = await navigator.mediaDevices.getUserMedia({{video: true, audio: false}});
        const vid = document.getElementById("camara");
        vid.srcObject = stream;
        document.getElementById("sin-camara").classList.add("hidden");
    }} catch (e) {{
        console.warn("Cámara no disponible:", e.message);
    }}
}}

// ── Polling de detecciones (actualiza lista cada 4s si hay horario activo) ─
function iniciarPolling() {{
    if (!HORARIO) return;
    intervalId = setInterval(async () => {{
        try {{
            const r = await fetch(`${{API}}/sesion/detecciones?horario_uid=${{HORARIO}}`);
            if (!r.ok) return;
            const detecciones = await r.json();
            detecciones.forEach(d => {{
                if (!marcados.has(d.estudiante_uid)) {{
                    marcados.add(d.estudiante_uid);
                    actualizarTarjeta(d.estudiante_uid, d.estado_asistencia);
                }}
            }});
            document.getElementById("contador").textContent = marcados.size;
        }} catch {{}}
    }}, 4000);
}}

function actualizarTarjeta(uid, estado) {{
    const el = document.getElementById(`alumno-${{uid}}`);
    if (!el) return;
    const etiquetas = {{
        presente:"Presente", tardanza:"Tardanza", falta:"Falta", justificada:"Justificada"
    }};
    const colores = {{
        presente:"bg-green-100 text-green-800",
        tardanza:"bg-yellow-100 text-yellow-800",
        falta:"bg-red-100 text-red-800",
        justificada:"bg-blue-100 text-blue-800",
    }};
    const badge = el.querySelector("span.rounded-full");
    if (badge) {{
        badge.className = `text-xs font-semibold px-2 py-0.5 rounded-full ${{colores[estado] || ""}}`;
        badge.textContent = etiquetas[estado] || estado;
    }}
    const btn = el.querySelector("button");
    if (btn) btn.remove();
    el.classList.add("slide-in");
}}

// ── Marcar presente manualmente ──────────────────────────────────────────
async function marcarPresente(estUid, matUid, horUid, btn) {{
    const docenteUid = localStorage.getItem("docente_uid") || "";
    if (!docenteUid) {{
        alert("Selecciona tu nombre de docente en el dashboard primero.");
        return;
    }}
    btn.disabled = true;
    btn.textContent = "Guardando…";
    try {{
        const r = await fetch(`${{API}}/sesion/marcar`, {{
            method:  "POST",
            headers: {{"Content-Type": "application/json"}},
            body:    JSON.stringify({{
                horario_uid:    horUid,
                estudiante_uid: estUid,
                matricula_uid:  matUid,
                docente_uid:    docenteUid,
                estado:         "presente",
            }}),
        }});
        const datos = await r.json();
        if (r.ok && datos.success) {{
            marcados.add(estUid);
            actualizarTarjeta(estUid, "presente");
            document.getElementById("contador").textContent = marcados.size;
        }} else {{
            btn.disabled = false;
            btn.textContent = "Reintentar";
            alert(datos.detail || "Error al registrar asistencia.");
        }}
    }} catch {{
        btn.disabled = false;
        btn.textContent = "Reintentar";
        alert("No se pudo conectar con el servidor.");
    }}
}}

// ── Finalizar sesión ─────────────────────────────────────────────────────
function finalizarSesion() {{
    if (!confirm("¿Deseas finalizar la sesión de asistencia? Se redirigirá al dashboard.")) return;
    if (intervalId) clearInterval(intervalId);
    const vid = document.getElementById("camara");
    if (vid && vid.srcObject) vid.srcObject.getTracks().forEach(t => t.stop());
    window.location.href = "/";
}}

// ── Inicio ───────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {{
    iniciarCamara();
    iniciarPolling();
}});
</script>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Rutas FastAPI
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/asistencia", response_class=HTMLResponse, include_in_schema=False)
def pagina_asistencia(
    seccion_uid: str = Query(default=""),
    horario_uid: str = Query(default=""),
):
    """
    Renderiza la página de toma de asistencia con datos reales.

    - Sin parámetros   → muestra solo el selector de sección
    - ?seccion_uid=X   → carga los horarios de hoy para esa sección
    - ?seccion_uid=X&horario_uid=Y → carga la lista de alumnos con estado
    """
    error: Optional[str] = None

    # Secciones: siempre se cargan
    secciones = _get("/sesion/secciones") or []
    if not secciones:
        error = "No se encontraron secciones activas. Verifica la conexión con el servidor."

    # Horarios del día para la sección seleccionada
    horarios: list = []
    if seccion_uid:
        horarios = _get(f"/sesion/horarios?seccion_uid={seccion_uid}") or []
        if seccion_uid and not horarios:
            error = "No hay clases programadas para hoy en esta sección."

    # Determinar horario actual seleccionado
    horario_actual: Optional[dict] = None
    if horario_uid and horarios:
        horario_actual = next((h for h in horarios if h["uid"] == horario_uid), None)
        if not horario_actual:
            error = "El horario seleccionado no existe o no corresponde a esta sección."
            horario_uid = ""

    # Alumnos con estado de asistencia
    alumnos: list = []
    if seccion_uid and horario_uid:
        alumnos = _get(
            f"/sesion/alumnos?seccion_uid={seccion_uid}&horario_uid={horario_uid}"
        ) or []

    html = _renderizar(
        secciones=secciones,
        horarios=horarios,
        alumnos=alumnos,
        horario_actual=horario_actual,
        seccion_uid=seccion_uid,
        horario_uid=horario_uid,
        error=error,
    )
    return HTMLResponse(content=html)
