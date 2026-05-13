// ═══════════════════════════════════════════════════════════════
// permiso_salida.seed.ts
// Genera ~30 permisos de retiro anticipado distribuidos en los
// últimos 60 días hábiles.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

const MOTIVOS = [
  'Cita médica urgente',
  'Control pediátrico programado',
  'Trámite familiar urgente',
  'Enfermedad leve — recogido por apoderado',
  'Viaje familiar imprevisto',
  'Emergencia familiar',
  'Consulta odontológica',
  'Examen médico especializado',
];

export async function seedPermisoSalida() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding permisos de salida...");

    const { rows: matriculas } = await client.query(
      `SELECT m.id AS matricula_id, rpe.padre_id
       FROM matricula m
       JOIN estudiante e ON e.id = m.estudiante_id
       JOIN relacion_padre_estudiante rpe ON rpe.estudiante_id = e.id
         AND rpe.es_apoderado_principal = TRUE
       WHERE m.estado = 'activa'`
    );

    const { rows: admins } = await client.query(
      `SELECT id FROM usuario WHERE rol IN ('auxiliar','admin')`
    );

    if (matriculas.length === 0) throw new Error("No hay matrículas con apoderado.");

    const seleccionados = faker.helpers.arrayElements(matriculas, Math.min(30, matriculas.length));
    let insertados = 0;

    for (const m of seleccionados) {
      const daysAgo  = faker.number.int({ min: 1, max: 60 });
      const fecha    = new Date();
      fecha.setDate(fecha.getDate() - daysAgo);
      // Solo días hábiles
      while (fecha.getDay() === 0 || fecha.getDay() === 6) fecha.setDate(fecha.getDate() - 1);
      const fechaStr = fecha.toISOString().split('T')[0];

      const hora = faker.number.int({ min: 9, max: 11 });
      const min  = faker.number.int({ min: 0, max: 59 });
      const horaSalida = `${fechaStr}T${String(hora).padStart(2,'0')}:${String(min).padStart(2,'0')}:00-05:00`;

      await client.query(
        `INSERT INTO permiso_salida
           (matricula_id, autorizado_por, registrado_por, fecha, hora_salida, motivo)
         VALUES ($1,$2,$3,$4,$5,$6)`,
        [
          m.matricula_id,
          m.padre_id,
          faker.helpers.arrayElement(admins).id,
          fechaStr,
          horaSalida,
          faker.helpers.arrayElement(MOTIVOS),
        ]
      );
      insertados++;
    }

    console.log(`✅ ${insertados} permisos de salida insertados`);
  } catch (error) {
    console.error("❌ Error seeding permiso_salida:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedPermisoSalida().then(() => process.exit(0)).catch(() => process.exit(1));
}
