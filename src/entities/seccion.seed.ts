// ═══════════════════════════════════════════════════════════════
// seccion.seed.ts
// Crea secciones reales de un colegio secundario peruano.
// Secciones para el año 2025.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";

export async function seedSeccion() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding secciones...");

    const { rows } = await client.query(
      `SELECT id FROM ano_escolar WHERE nombre = '2025'`
    );
    const anoId = rows[0].id;

    // Grados típicos de secundaria peruana (1.° al 5.°), secciones A y B
    const secciones = [
      ['1.° Secundaria', 'Secundaria', 'A'],
      ['1.° Secundaria', 'Secundaria', 'B'],
      ['2.° Secundaria', 'Secundaria', 'A'],
      ['2.° Secundaria', 'Secundaria', 'B'],
      ['3.° Secundaria', 'Secundaria', 'A'],
      ['3.° Secundaria', 'Secundaria', 'B'],
      ['4.° Secundaria', 'Secundaria', 'A'],
      ['4.° Secundaria', 'Secundaria', 'B'],
      ['5.° Secundaria', 'Secundaria', 'A'],
      ['5.° Secundaria', 'Secundaria', 'B'],
    ];

    for (const [grado, nivel, codigo] of secciones) {
      await client.query(
        `INSERT INTO seccion (ano_escolar_id, grado, nivel, codigo) VALUES ($1,$2,$3,$4)`,
        [anoId, grado, nivel, codigo]
      );
    }

    console.log(`✅ ${secciones.length} secciones insertadas`);
  } catch (error) {
    console.error("❌ Error seeding seccion:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedSeccion().then(() => process.exit(0)).catch(() => process.exit(1));
}
