// ═══════════════════════════════════════════════════════════════
// asistencia_clase.seed.ts
// Genera asistencias por período de clase para los últimos 60 días hábiles.
// Solo genera para los horarios cuyo dia_semana coincide con la fecha.
// Distribución: 88% presente, 7% ausente, 4% fuga, 1% justificado
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

const MAP_DIA: Record<number, string> = {
  1:'lunes', 2:'martes', 3:'miercoles', 4:'jueves', 5:'viernes',
};

function diasHabiles(cantidad: number): Date[] {
  const dias: Date[] = [];
  const cursor = new Date();
  while (dias.length < cantidad) {
    cursor.setDate(cursor.getDate() - 1);
    if (cursor.getDay() >= 1 && cursor.getDay() <= 5) dias.push(new Date(cursor));
  }
  return dias.reverse();
}

export async function seedAsistenciaClase() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding asistencia_clase...");

    const fechas = diasHabiles(60);

    // Obtener horarios con la sección y docente
    const { rows: horarios } = await client.query(
      `SELECT hc.id AS horario_id, hc.seccion_id, hc.dia_semana, hc.docente_id,
              d.usuario_id AS docente_usuario_id
       FROM horario_clase hc
       JOIN docente d ON d.id = hc.docente_id`
    );

    // Obtener matrículas por sección
    const { rows: matriculas } = await client.query(
      `SELECT id AS matricula_id, seccion_id FROM matricula WHERE estado='activa'`
    );

    // Agrupar matrículas por sección para lookup rápido
    const matriculasPorSeccion = new Map<number, number[]>();
    for (const m of matriculas) {
      const lista = matriculasPorSeccion.get(m.seccion_id) || [];
      lista.push(m.matricula_id);
      matriculasPorSeccion.set(m.seccion_id, lista);
    }

    let insertados = 0;

    for (const fecha of fechas) {
      const diaNombre = MAP_DIA[fecha.getDay()];
      if (!diaNombre) continue;

      const fechaStr = fecha.toISOString().split('T')[0];

      // Solo los horarios que corresponden a este día de la semana
      const horariosDelDia = horarios.filter(h => h.dia_semana === diaNombre);

      for (const h of horariosDelDia) {
        const alumnos = matriculasPorSeccion.get(h.seccion_id) || [];

        for (const matriculaId of alumnos) {
          const rand = Math.random();
          let estado: string;

          if (rand < 0.88)      estado = 'presente';
          else if (rand < 0.95) estado = 'ausente';
          else if (rand < 0.99) estado = 'fuga';
          else                  estado = 'justificado';

          await client.query(
            `INSERT INTO asistencia_clase
               (matricula_id, horario_clase_id, fecha, estado, registrado_por)
             VALUES ($1,$2,$3,$4,$5)
             ON CONFLICT DO NOTHING`,
            [matriculaId, h.horario_id, fechaStr, estado, h.docente_usuario_id]
          );
          insertados++;
        }
      }
    }

    console.log(`✅ ${insertados} registros de asistencia_clase insertados`);
  } catch (error) {
    console.error("❌ Error seeding asistencia_clase:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedAsistenciaClase().then(() => process.exit(0)).catch(() => process.exit(1));
}
