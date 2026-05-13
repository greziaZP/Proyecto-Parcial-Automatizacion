// ═══════════════════════════════════════════════════════════════
// manager.seed.ts
// Orquestador principal. Ejecuta todos los seeders en el ORDEN
// CORRECTO de dependencias de FK. Si uno falla, se detiene todo.
//
// Orden:
//   Nivel 1 (sin FK):        ano_escolar, curso, usuario
//   Nivel 2 (depende de 1):  periodo, seccion, estudiante, docente, padre
//   Nivel 3 (depende de 2):  relacion_padre_est, matricula, horario_clase
//   Nivel 4 (depende de 3):  registro_ingreso, asistencia_clase
//   Nivel 5 (depende de 4):  fuga, permiso_salida, justificacion
//   Nivel 6 (depende de 5):  nota_actitudinal
// ═══════════════════════════════════════════════════════════════
import { pool } from "./config";

import { seedAnoEscolar }              from "./entities/ano_escolar.seed";
import { seedPeriodoTrimestral }       from "./entities/periodo_trimestral.seed";
import { seedSeccion }                 from "./entities/seccion.seed";
import { seedCurso }                   from "./entities/curso.seed";
import { seedUsuario }                 from "./entities/usuario.seed";
import { seedEstudiante }              from "./entities/estudiante.seed";
import { seedDocente }                 from "./entities/docente.seed";
import { seedPadreFamilia }            from "./entities/padre_familia.seed";
import { seedRelacionPadreEstudiante } from "./entities/relacion_padre_estudiante.seed";
import { seedMatricula }               from "./entities/matricula.seed";
import { seedHorarioClase }            from "./entities/horario_clase.seed";
import { seedRegistroIngreso }         from "./entities/registro_ingreso.seed";
import { seedAsistenciaClase }         from "./entities/asistencia_clase.seed";
import { seedFuga }                    from "./entities/fuga.seed";
import { seedPermisoSalida }           from "./entities/permiso_salida.seed";
import { seedJustificacion }           from "./entities/justificacion.seed";
import { seedNotaActitudinal }         from "./entities/nota_actitudinal.seed";

async function runAllSeeders() {
  try {
    console.log("🚀 Iniciando seeding completo del sistema de asistencia...\n");
    console.log("━".repeat(55));

    // ── NIVEL 1: Sin dependencias ──────────────────────────────
    console.log("\n📦 Nivel 1 — Estructura académica y usuarios base\n");
    await seedAnoEscolar();
    await seedCurso();
    await seedUsuario();          // ← Aquí van los 2 "reales" del equipo

    // ── NIVEL 2: Dependen de nivel 1 ──────────────────────────
    console.log("\n📦 Nivel 2 — Períodos, secciones y personas\n");
    await seedPeriodoTrimestral();
    await seedSeccion();
    await seedEstudiante();
    await seedDocente();
    await seedPadreFamilia();

    // ── NIVEL 3: Dependen de nivel 2 ──────────────────────────
    console.log("\n📦 Nivel 3 — Matrículas, horarios y vínculos\n");
    await seedRelacionPadreEstudiante();
    await seedMatricula();
    await seedHorarioClase();

    // ── NIVEL 4: Registros de asistencia ─────────────────────
    console.log("\n📦 Nivel 4 — Registros de asistencia\n");
    await seedRegistroIngreso();
    await seedAsistenciaClase();

    // ── NIVEL 5: Fugas, permisos y justificaciones ────────────
    console.log("\n📦 Nivel 5 — Gestión de fugas, permisos y justificaciones\n");
    await seedFuga();
    await seedPermisoSalida();
    await seedJustificacion();

    // ── NIVEL 6: Notas actitudinales ─────────────────────────
    console.log("\n📦 Nivel 6 — Notas actitudinales\n");
    await seedNotaActitudinal();

    console.log("\n" + "━".repeat(55));
    console.log("✅ ¡Seeding completo exitosamente!");
    console.log("\n📊 Resumen aproximado:");
    console.log("   • 2 años escolares (2025 activo, 2024 histórico)");
    console.log("   • 3 períodos trimestrales");
    console.log("   • 10 secciones");
    console.log("   • 12 cursos");
    console.log("   • ~113 usuarios (2 reales + 111 faker)");
    console.log("   • 80 estudiantes, 15 docentes, 15 padres");
    console.log("   • ~80 matrículas activas");
    console.log("   • ~60+ bloques de horario");
    console.log("   • 4,800+ registros de ingreso (60 días × 80 alumnos)");
    console.log("   • ~10,000+ registros de asistencia_clase");
    console.log("   • ~400+ fugas detectadas");
    console.log("   • ~30 permisos de salida");
    console.log("   • ~40 justificaciones");
    console.log("   • ~240 notas actitudinales (80 alumnos × 3 períodos)");

  } catch (error) {
    console.error("\n❌ Seeding falló:", error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

runAllSeeders().then(() => process.exit(0));
