// ═══════════════════════════════════════════════════════════════
// matricula.seed.ts
// Distribuye los 80 estudiantes entre las 10 secciones del año 2025.
// Cada estudiante se matricula en una sola sección (UNIQUE constraint).
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedMatricula() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding matrículas...");

    // Solo secciones del año activo (2025)
    const { rows: secciones } = await client.query(
      `SELECT s.id FROM seccion s
       JOIN ano_escolar a ON a.id = s.ano_escolar_id
       WHERE a.nombre = '2025'`
    );

    const { rows: estudiantes } = await client.query(`SELECT id FROM estudiante`);

    if (secciones.length === 0) throw new Error("No hay secciones.");
    if (estudiantes.length === 0) throw new Error("No hay estudiantes.");

    let insertados = 0;

    for (const est of estudiantes) {
      // Asignar sección aleatoria al estudiante
      const seccion = faker.helpers.arrayElement(secciones);

      await client.query(
        `INSERT INTO matricula (estudiante_id, seccion_id, estado)
         VALUES ($1,$2,'activa')
         ON CONFLICT DO NOTHING`, // Si ya existe el par (estudiante, seccion), lo ignora
        [est.id, seccion.id]
      );
      insertados++;
    }

    console.log(`✅ ${insertados} matrículas insertadas`);
  } catch (error) {
    console.error("❌ Error seeding matricula:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedMatricula().then(() => process.exit(0)).catch(() => process.exit(1));
}
