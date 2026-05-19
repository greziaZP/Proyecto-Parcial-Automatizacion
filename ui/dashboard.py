"""
ui/dashboard.py — Dashboard del docente con renderizado server-side.

El servidor (Python) consulta la API, procesa los datos y entrega
el HTML ya armado con información real. Sin spinners de carga inicial.
"""
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

router = APIRouter()
API_BASE = "http://localhost:8000"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers Python (lógica de negocio en el servidor)
# ──────────────────────────────────────────────────────────────────────────────

_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_DIAS_SEMANA = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]


def _saludo() -> str:
    hora = datetime.now().hour
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def _fecha_legible() -> str:
    ahora = datetime.now()
    dia_semana = _DIAS_SEMANA[ahora.weekday()]
    return f"{dia_semana.capitalize()}, {ahora.day} de {_MESES[ahora.month - 1]} de {ahora.year}"


def _hora_actual() -> str:
    return datetime.now().strftime("%H:%M")


def _estado_clase(hora_ini: str, hora_fin: str) -> str:
    """Determina si una clase está activa, pendiente o finalizada."""
    ahora = _hora_actual()
    if hora_ini <= ahora <= hora_fin:
        return "activa"
    if hora_fin < ahora:
        return "finalizada"
    return "pendiente"


def _consultar_api(ruta: str) -> Optional[dict | list]:
    """Consulta un endpoint de la API. Retorna None si falla."""
    try:
        with httpx.Client(timeout=4.0) as cliente:
            respuesta = cliente.get(f"{API_BASE}{ruta}")
            respuesta.raise_for_status()
            return respuesta.json()
    except httpx.ConnectError:
        return None
    except Exception:
        return None


def _obtener_datos_dashboard() -> dict:
    """Consulta la API server-side y retorna todos los datos del dashboard."""
    proxima = _consultar_api("/dashboard/proxima-clase") or {}
    clases  = _consultar_api("/dashboard/horario-hoy")   or []
    stats   = _consultar_api("/dashboard/stats") or {
        "total": 0, "a_tiempo": 0, "tardanza": 0, "ausente": 0,
    }
    docentes = _consultar_api("/sesion/docentes") or []

    # Enriquecer clases con estado calculado en Python
    for clase in clases:
        clase["_estado"] = _estado_clase(
            clase.get("hora_inicio", ""), clase.get("hora_fin", "")
        )

    # Porcentajes para barras de estadísticas
    total = stats.get("total") or 1
    stats["pct_a_tiempo"] = round(stats.get("a_tiempo", 0) / total * 100)
    stats["pct_tardanza"] = round(stats.get("tardanza", 0) / total * 100)
    stats["pct_ausente"]  = round(stats.get("ausente",  0) / total * 100)

    return {
        "proxima":  proxima,
        "clases":   clases,
        "stats":    stats,
        "docentes": docentes,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Generadores de fragmentos HTML
# ──────────────────────────────────────────────────────────────────────────────

def _html_cta_proxima_clase(proxima: dict) -> str:
    """Genera la tarjeta CTA de la próxima clase."""
    if not proxima or not proxima.get("uid"):
        return """
        <div class="flex flex-col items-center justify-center py-12 text-on-surface-variant">
            <span class="material-symbols-outlined text-5xl mb-3 opacity-40">event_available</span>
            <p class="text-body-lg font-semibold">No hay clases programadas para hoy</p>
            <p class="text-body-md opacity-60 mt-1">Disfruta tu día libre</p>
        </div>"""

    tiempo_restante = ""
    hora_ini = proxima.get("hora_inicio", "")
    ahora    = _hora_actual()
    if hora_ini > ahora:
        h, m = hora_ini.split(":")
        ah, am = ahora.split(":")
        mins_restantes = (int(h) * 60 + int(m)) - (int(ah) * 60 + int(am))
        if mins_restantes <= 30:
            tiempo_restante = f'<span class="inline-block bg-error-container text-on-error-container font-semibold text-xs px-3 py-1 rounded-full mb-4">Inicia en {mins_restantes} min</span>'
        else:
            tiempo_restante = f'<span class="inline-block bg-surface-container text-on-surface-variant font-semibold text-xs px-3 py-1 rounded-full mb-4">Próxima clase</span>'
    else:
        tiempo_restante = '<span class="inline-block bg-primary/10 text-primary font-semibold text-xs px-3 py-1 rounded-full mb-4">En curso ahora</span>'

    link_asistencia = (
        f"/asistencia?seccion_uid={proxima.get('seccion_uid', '')}"
        f"&horario_uid={proxima.get('uid', '')}"
    )

    return f"""
    <div class="flex justify-between items-start mb-8">
        <div>
            {tiempo_restante}
            <h3 class="text-2xl font-bold text-on-background mb-1">{proxima.get("curso_nombre", "—")}</h3>
            <p class="text-body-md text-on-surface-variant flex items-center gap-2">
                <span class="material-symbols-outlined text-base">group</span>
                {proxima.get("seccion_label", "—")} &nbsp;·&nbsp;
                <span class="material-symbols-outlined text-base">person</span>
                {proxima.get("docente_nombre", "—")}
            </p>
        </div>
        <div class="text-right">
            <p class="text-xl font-bold text-primary">{proxima.get("hora_inicio", "—")}</p>
            <p class="text-body-md text-on-surface-variant">hasta {proxima.get("hora_fin", "—")}</p>
        </div>
    </div>
    <div class="flex justify-between items-center">
        <p class="text-body-md text-on-surface-variant flex items-center gap-2">
            <span class="material-symbols-outlined text-base text-primary">people</span>
            <span class="font-bold text-primary">{proxima.get("total_alumnos", "—")}</span> alumnos matriculados
        </p>
        <a href="{link_asistencia}"
           class="bg-primary text-white px-6 py-3 rounded-lg font-semibold text-sm
                  hover:bg-primary/90 active:scale-95 transition-all flex items-center gap-2 shadow-sm">
            <span class="material-symbols-outlined text-xl">face</span>
            Iniciar Escaneo Facial
        </a>
    </div>"""


def _html_item_clase(clase: dict) -> str:
    """Genera una fila en la lista de clases del día."""
    estado = clase.get("_estado", "pendiente")
    icono  = {"activa": "play_circle", "finalizada": "check_circle", "pendiente": "schedule"}[estado]
    color_icono = {
        "activa":    "text-primary fill",
        "finalizada":"text-on-surface-variant",
        "pendiente": "text-on-surface-variant",
    }[estado]
    badge = {
        "activa":    '<span class="text-xs font-bold text-primary border border-primary px-2 py-0.5 rounded">En Curso</span>',
        "finalizada":'<span class="text-xs text-on-surface-variant">Finalizada</span>',
        "pendiente": '<span class="text-xs text-on-surface-variant border border-outline-variant px-2 py-0.5 rounded">Pendiente</span>',
    }[estado]

    borde_activa = '<div class="absolute left-[-24px] top-0 bottom-0 w-1 bg-primary rounded-r-full"></div>' if estado == "activa" else ""

    link = ""
    if estado in ("activa", "pendiente"):
        link_url = f"/asistencia?seccion_uid={clase.get('seccion_uid', '')}&horario_uid={clase.get('uid', '')}"
        link = f'<a href="{link_url}" class="text-xs text-primary hover:underline ml-2">→ Asistencia</a>'

    return f"""
    <div class="flex items-center gap-4 py-4 border-b border-outline-variant last:border-0 relative">
        {borde_activa}
        <div class="w-11 h-11 rounded-lg bg-surface-container flex items-center justify-center border border-outline-variant shrink-0">
            <span class="material-symbols-outlined {color_icono}">{icono}</span>
        </div>
        <div class="flex-1 min-w-0">
            <h4 class="text-sm font-bold text-on-background truncate">{clase.get("curso_nombre", "—")}</h4>
            <p class="text-xs text-on-surface-variant truncate">
                {clase.get("hora_inicio", "—")} – {clase.get("hora_fin", "—")} &nbsp;·&nbsp; {clase.get("seccion_label", "—")}
            </p>
        </div>
        <div class="text-right shrink-0">
            {badge}{link}
        </div>
    </div>"""


def _html_stats(stats: dict) -> str:
    """Genera el bloque de estadísticas de ingreso del día."""
    items = [
        ("A tiempo",  stats.get("a_tiempo", 0), stats.get("pct_a_tiempo", 0), "bg-primary",   "text-primary",   "check_circle"),
        ("Tardanzas", stats.get("tardanza",  0), stats.get("pct_tardanza", 0), "bg-secondary", "text-secondary", "schedule"),
        ("Ausentes",  stats.get("ausente",   0), stats.get("pct_ausente",  0), "bg-error",     "text-error",     "cancel"),
    ]
    filas = ""
    for etiqueta, valor, pct, bg, color_text, icono in items:
        filas += f"""
        <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-lg {color_text}">{icono}</span>
            <div class="flex-1">
                <div class="flex justify-between mb-1">
                    <span class="text-xs text-on-surface-variant">{etiqueta}</span>
                    <span class="text-xs font-bold {color_text}">{valor}</span>
                </div>
                <div class="h-1.5 bg-surface-container rounded-full overflow-hidden">
                    <div class="h-full {bg} rounded-full" style="width:{pct}%"></div>
                </div>
            </div>
        </div>"""
    return f"""
    <div class="flex flex-col gap-4">
        <p class="text-xs text-on-surface-variant">Total registros: <span class="font-bold text-on-surface">{stats.get("total", 0)}</span></p>
        {filas}
    </div>"""


def _html_opciones_docentes(docentes: list) -> str:
    """Genera las opciones del select de docentes."""
    opciones = '<option value="">— Selecciona tu nombre —</option>'
    for d in docentes:
        opciones += f'<option value="{d["uid"]}">{d["nombres"]} {d["apellidos"]}</option>'
    return opciones


# ──────────────────────────────────────────────────────────────────────────────
# Ensamblado final del HTML
# ──────────────────────────────────────────────────────────────────────────────

_CSS_ANIMACIONES = """
<style>
    @keyframes fadeInUp {
        from { opacity:0; transform:translateY(10px); }
        to   { opacity:1; transform:translateY(0); }
    }
    .fade-in { animation: fadeInUp 0.35s ease-out forwards; }
    .material-symbols-outlined { font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24; }
    .material-symbols-outlined.fill { font-variation-settings:'FILL' 1,'wght' 400,'GRAD' 0,'opsz' 24; }
</style>
"""

_TAILWIND_COLORS = """
"primary":"#002068","on-primary":"#ffffff","primary-container":"#003399",
"on-primary-container":"#8aa4ff","secondary":"#00668a","on-secondary":"#ffffff",
"secondary-container":"#40c2fd","error":"#ba1a1a","on-error":"#ffffff",
"error-container":"#ffdad6","on-error-container":"#93000a",
"background":"#f8f9ff","on-background":"#0b1c30","surface":"#f8f9ff",
"on-surface":"#0b1c30","surface-variant":"#d3e4fe","on-surface-variant":"#444653",
"surface-container-lowest":"#ffffff","surface-container-low":"#eff4ff",
"surface-container":"#e5eeff","surface-container-high":"#dce9ff",
"surface-container-highest":"#d3e4fe","outline":"#747684","outline-variant":"#c4c5d5"
"""


def _renderizar_dashboard(datos: dict) -> str:
    proxima  = datos["proxima"]
    clases   = datos["clases"]
    stats    = datos["stats"]
    docentes = datos["docentes"]

    html_cta     = _html_cta_proxima_clase(proxima)
    html_clases  = "".join(_html_item_clase(c) for c in clases) if clases else (
        '<p class="text-body-md text-on-surface-variant py-6 text-center">No hay clases programadas para hoy.</p>'
    )
    html_stats   = _html_stats(stats)
    html_docentes = _html_opciones_docentes(docentes)
    total_clases = len(clases)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Dashboard — Asistencia Biométrica · Narváez</title>
    <meta name="description" content="Panel principal del sistema de asistencia biométrica. Consulta las clases del día, estadísticas y accede al escaneo facial."/>
    <script src="https://cdn.tailwindcss.com?plugins=forms"></script>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap" rel="stylesheet"/>
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <script>
        tailwind.config = {{
            theme: {{ extend: {{ colors: {{ {_TAILWIND_COLORS} }},
                fontFamily: {{ DEFAULT: ["Manrope", "sans-serif"] }} }} }}
        }}
    </script>
    {_CSS_ANIMACIONES}
</head>
<body class="bg-background text-on-background min-h-screen antialiased" style="font-family:'Manrope',sans-serif">

<!-- Sidebar -->
<aside class="h-screen w-64 fixed left-0 top-0 flex flex-col bg-surface-container-lowest shadow-lg z-50 py-8">
    <div class="px-6 mb-8 flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white font-bold text-lg">N</div>
        <div>
            <p class="font-bold text-primary text-base leading-tight">Narváez</p>
            <p class="text-xs text-on-surface-variant">Asistencia Biométrica</p>
        </div>
    </div>
    <nav class="flex-1 px-4 space-y-1">
        <a href="/" class="flex items-center gap-3 px-4 py-3 rounded-xl bg-primary/10 text-primary font-semibold">
            <span class="material-symbols-outlined fill">dashboard</span>
            <span class="text-sm">Dashboard</span>
        </a>
        <a href="/asistencia" class="flex items-center gap-3 px-4 py-3 rounded-xl text-on-surface-variant hover:bg-surface-container hover:text-primary transition-colors">
            <span class="material-symbols-outlined">face</span>
            <span class="text-sm">Tomar Asistencia</span>
        </a>
    </nav>
    <!-- Selector docente sin login -->
    <div class="px-4 mt-4">
        <div class="p-3 rounded-xl bg-surface-container-low border border-outline-variant">
            <label class="text-xs text-on-surface-variant block mb-1 font-semibold">Docente activo</label>
            <select id="sel-docente"
                    onchange="guardarDocente(this)"
                    class="w-full text-sm text-on-surface bg-transparent outline-none cursor-pointer font-semibold">
                {html_docentes}
            </select>
        </div>
        <p class="text-xs text-on-surface-variant mt-2 px-1">
            <span class="material-symbols-outlined text-xs align-middle">info</span>
            Sin inicio de sesión por ahora
        </p>
    </div>
</aside>

<!-- Contenido principal -->
<main class="ml-64 px-8 py-10 max-w-6xl">

    <!-- Encabezado -->
    <header class="flex justify-between items-end mb-8 fade-in">
        <div>
            <p class="text-xs text-on-surface-variant uppercase tracking-widest mb-1">{_fecha_legible()}</p>
            <h2 class="text-3xl font-bold text-primary" id="titular">{_saludo()}</h2>
            <p class="text-sm text-on-surface-variant mt-1">
                Hora actual: <span class="font-bold text-on-surface" id="reloj">{_hora_actual()}</span>
            </p>
        </div>
        <!-- KPIs -->
        <div class="flex gap-3">
            <div class="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-outline-variant shadow-sm">
                <span class="material-symbols-outlined text-primary text-lg fill">check_circle</span>
                <div>
                    <p class="text-sm font-bold text-primary">{stats.get("a_tiempo", 0)}</p>
                    <p class="text-[10px] text-on-surface-variant">A tiempo</p>
                </div>
            </div>
            <div class="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-outline-variant shadow-sm">
                <span class="material-symbols-outlined text-secondary text-lg">schedule</span>
                <div>
                    <p class="text-sm font-bold text-secondary">{stats.get("tardanza", 0)}</p>
                    <p class="text-[10px] text-on-surface-variant">Tardanzas</p>
                </div>
            </div>
            <div class="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-outline-variant shadow-sm">
                <span class="material-symbols-outlined text-error text-lg">cancel</span>
                <div>
                    <p class="text-sm font-bold text-error">{stats.get("ausente", 0)}</p>
                    <p class="text-[10px] text-on-surface-variant">Ausentes</p>
                </div>
            </div>
        </div>
    </header>

    <!-- Cuadrícula principal -->
    <div class="grid grid-cols-12 gap-6">

        <!-- CTA Próxima clase -->
        <section class="col-span-12 lg:col-span-8 bg-white rounded-2xl p-6 shadow-sm border border-outline-variant relative overflow-hidden fade-in">
            <div class="absolute top-0 right-0 w-48 h-full bg-gradient-to-l from-surface-container to-transparent opacity-40 pointer-events-none"></div>
            <div class="relative z-10">
                {html_cta}
            </div>
        </section>

        <!-- Estadísticas -->
        <section class="col-span-12 lg:col-span-4 bg-white rounded-2xl p-6 shadow-sm border border-outline-variant fade-in">
            <h3 class="font-bold text-base text-on-background mb-4">Ingresos del Día</h3>
            {html_stats}
        </section>

        <!-- Clases del día -->
        <section class="col-span-12 lg:col-span-7 bg-white rounded-2xl p-6 shadow-sm border border-outline-variant fade-in">
            <div class="flex justify-between items-center mb-4 pb-4 border-b border-outline-variant">
                <h3 class="font-bold text-base text-on-background">Clases de Hoy</h3>
                <span class="text-xs bg-surface-container text-on-surface-variant px-2 py-1 rounded-lg">
                    {total_clases} clase{"s" if total_clases != 1 else ""}
                </span>
            </div>
            <div class="overflow-y-auto max-h-72">
                {html_clases}
            </div>
        </section>

        <!-- Acceso rápido -->
        <section class="col-span-12 lg:col-span-5 bg-white rounded-2xl p-6 shadow-sm border border-outline-variant fade-in">
            <h3 class="font-bold text-base text-on-background mb-4">Acceso Rápido</h3>
            <div class="grid grid-cols-2 gap-3">
                <a href="/asistencia"
                   class="flex flex-col items-center gap-2 p-4 rounded-xl bg-surface-container hover:bg-surface-container-high
                          border border-outline-variant transition-all hover:shadow-md group">
                    <div class="w-11 h-11 rounded-xl bg-primary flex items-center justify-center group-hover:scale-110 transition-transform">
                        <span class="material-symbols-outlined text-white">face</span>
                    </div>
                    <span class="text-xs font-semibold text-center text-on-surface">Tomar Asistencia</span>
                </a>
                <a href="/asistencia"
                   class="flex flex-col items-center gap-2 p-4 rounded-xl bg-surface-container hover:bg-surface-container-high
                          border border-outline-variant transition-all hover:shadow-md group">
                    <div class="w-11 h-11 rounded-xl bg-secondary flex items-center justify-center group-hover:scale-110 transition-transform">
                        <span class="material-symbols-outlined text-white">bar_chart</span>
                    </div>
                    <span class="text-xs font-semibold text-center text-on-surface">Ver Reporte</span>
                </a>
            </div>
        </section>

    </div>
</main>

<script>
    // Reloj en tiempo real
    function actualizarReloj() {{
        const ahora = new Date();
        document.getElementById("reloj").textContent =
            ahora.toLocaleTimeString("es-PE", {{hour:"2-digit", minute:"2-digit"}});
    }}
    setInterval(actualizarReloj, 1000);

    // Guardar docente seleccionado en localStorage
    function guardarDocente(sel) {{
        localStorage.setItem("docente_uid",    sel.value);
        localStorage.setItem("docente_nombre", sel.options[sel.selectedIndex].text);
        const nombre = sel.options[sel.selectedIndex].text;
        if (nombre && sel.value) {{
            const hora = new Date().getHours();
            const saludo = hora < 12 ? "Buenos días" : hora < 19 ? "Buenas tardes" : "Buenas noches";
            document.getElementById("titular").textContent = saludo + ", " + nombre.split(" ")[0];
        }}
    }}

    // Restaurar docente guardado al cargar
    document.addEventListener("DOMContentLoaded", () => {{
        const uid = localStorage.getItem("docente_uid");
        const sel = document.getElementById("sel-docente");
        if (uid && sel) {{
            sel.value = uid;
            if (sel.value) guardarDocente(sel);
        }}
    }});
</script>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Ruta FastAPI
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def pagina_dashboard():
    """
    Renderiza el dashboard con datos reales del servidor.
    Python consulta la API, procesa la información y devuelve el HTML listo.
    """
    datos = _obtener_datos_dashboard()
    return HTMLResponse(content=_renderizar_dashboard(datos))
