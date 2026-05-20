"""
manager.py — Orquestador principal del seeder Python (v3)
=========================================================
Ejecuta TODOS los seeders en el orden correcto de dependencias FK.
Si un paso falla, se detiene inmediatamente (fail-fast).

Uso:
    .venv/bin/python manager.py

Variables de entorno para parametrizar (ver config.py):
    SEED_NUM_DOCENTES, SEED_NUM_AUXILIARES, SEED_NUM_ESTUDIANTES,
    SEED_NUM_PADRES, SEED_DIAS_HISTORIAL, SEED_PCT_TARDANZA, etc.

Orden de ejecución:
  Nivel 1 — Catálogos base (sin FK):
      ano_escolar, curso
  Nivel 2 — Auth:
      usuario
  Nivel 3 — Perfiles 1:1 (shared UUID PK):
      docente, auxiliar, padre_familia, estudiante
  Nivel 4 — Puente M:N:
      relacion_padre_estudiante
  Nivel 5 — Estructura académica:
      seccion, periodo_trimestral, matricula  ← incluye UPDATE estudiante.matricula_actual_uid
      horario_clase
  Nivel 6 — Permisos:
      permiso_salida
  Nivel 7 — Asistencia (sin justificacion_uid aún):
      registro_ingreso, asistencia_clase
  Nivel 8 — Justificaciones (NOT NULL → apunta a asistencia_clase existente):
      justificacion  ← actualiza también asistencia_clase.justificacion_uid
                       y registro_ingreso.justificacion_uid
  Nivel 9 — Incidencias y evaluación:
      fuga, nota_actitudinal
"""

import sys
import time
from pathlib import Path


# Asegurar que config.py sea importable
sys.path.insert(0, str(Path(__file__).parent))

from config import close_pool, SeedConfig

from seeds.ano_escolar             import seed_ano_escolar
from seeds.curso                   import seed_curso
from seeds.usuario                 import seed_usuario
from seeds.perfiles                import (seed_docente, seed_auxiliar,
                                           seed_padre_familia, seed_estudiante)
from seeds.relacion_padre_estudiante import seed_relacion_padre_estudiante
from seeds.estructura_academica    import (seed_seccion, seed_periodo_trimestral,
                                           seed_matricula, seed_horario_clase)
from seeds.permiso_salida          import seed_permiso_salida
from seeds.asistencia              import seed_registro_ingreso, seed_asistencia_clase
from seeds.justificacion           import seed_justificacion
from seeds.fuga                    import seed_fuga
from seeds.nota_actitudinal        import seed_nota_actitudinal
from seeds.citacion                import seed_citacion


def _paso(nombre: str, fn, *args, **kwargs):
    """Ejecuta un seeder midiendo el tiempo y manejando errores."""
    print(f"\n{'─'*55}")
    t0 = time.time()
    result = fn(*args, **kwargs)
    elapsed = time.time() - t0
    print(f"   ⏱  {elapsed:.1f}s")
    return result


def run_all():
    inicio_total = time.time()
    print("🚀 Iniciando seeding completo — Sistema de Asistencia v3")
    print("=" * 55)
    SeedConfig.print_resumen()
    print("=" * 55)

    try:
        # ── NIVEL 1: Catálogos base ────────────────────────────────────────────
        print("\n📦 NIVEL 1 — Catálogos base")
        _paso("ano_escolar",  seed_ano_escolar)
        _paso("curso",        seed_curso)

        # ── NIVEL 2: Auth ──────────────────────────────────────────────────────
        print("\n📦 NIVEL 2 — Usuarios")
        _paso("usuario",      seed_usuario)

        # ── NIVEL 3: Perfiles 1:1 ──────────────────────────────────────────────
        print("\n📦 NIVEL 3 — Perfiles 1:1 (UUID shared PK)")
        _paso("docente",      seed_docente)
        _paso("auxiliar",     seed_auxiliar)
        _paso("padre_familia",seed_padre_familia)
        _paso("estudiante",   seed_estudiante)   # matricula_actual_uid = NULL aún

        # ── NIVEL 4: Relación M:N ──────────────────────────────────────────────
        print("\n📦 NIVEL 4 — Vínculos padre-estudiante")
        _paso("relacion",     seed_relacion_padre_estudiante)

        # ── NIVEL 5: Estructura académica ──────────────────────────────────────
        print("\n📦 NIVEL 5 — Estructura académica")
        _paso("seccion",           seed_seccion)
        _paso("periodo_trimestral",seed_periodo_trimestral)
        _paso("matricula",         seed_matricula)   # ← UPDATE matricula_actual_uid aquí
        _paso("horario_clase",     seed_horario_clase)

        # ── NIVEL 6: Permisos ──────────────────────────────────────────────────
        # print("\n📦 NIVEL 6 — Permisos de salida")
        # _paso("permiso_salida",    seed_permiso_salida)

        # # ── NIVEL 7: Asistencia ────────────────────────────────────────────────
        # print("\n📦 NIVEL 7 — Registros de asistencia")
        # _paso("registro_ingreso",  seed_registro_ingreso)
        # _paso("asistencia_clase",  seed_asistencia_clase)

        # # ── NIVEL 8: Justificaciones ───────────────────────────────────────────
        # print("\n📦 NIVEL 8 — Justificaciones")
        # _paso("justificacion",     seed_justificacion)  # actualiza FKs en asistencia y ingreso

        # # ── NIVEL 9: Incidencias y evaluación ─────────────────────────────────
        # print("\n📦 NIVEL 9 — Fugas y notas actitudinales")
        # _paso("fuga",              seed_fuga)
        # _paso("nota_actitudinal",  seed_nota_actitudinal)

        # # ── NIVEL 10: Citaciones ───────────────────────────────────────────────
        # print("\n📦 NIVEL 10 — Citaciones")
        # _paso("citacion",          seed_citacion)

        # ── Resumen final ──────────────────────────────────────────────────────
        total_s = time.time() - inicio_total
        print(f"\n{'='*55}")
        print(f"🎉 ¡Seeding completo en {total_s:.1f}s!")
        print(f"{'='*55}")
        print("\n📊 Volumen aproximado generado:")
        print(f"   • 2 años escolares (2024 histórico, 2025 activo)")
        print(f"   • 3 períodos trimestrales")
        print(f"   • {SeedConfig.NUM_SECCIONES} secciones")
        print(f"   • 12 cursos")
        print(f"   • {2 + SeedConfig.NUM_DOCENTES + SeedConfig.NUM_AUXILIARES + SeedConfig.NUM_ESTUDIANTES + SeedConfig.NUM_PADRES} usuarios")
        print(f"   • {SeedConfig.NUM_ESTUDIANTES} matrículas activas")
        print(f"   • {SeedConfig.NUM_ESTUDIANTES * SeedConfig.DIAS_HISTORIAL:,} registros de ingreso aprox.")
        print(f"   • Justificaciones, fugas y notas actitudinales calculadas")

    except Exception as e:
        print(f"\n❌ Seeding interrumpido: {e}")
        sys.exit(1)
    finally:
        close_pool()


if __name__ == "__main__":
    run_all()
    sys.exit(0)
