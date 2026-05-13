// ═══════════════════════════════════════════════════════════════
// periodo_trimestral.seed.ts
// Inserta los 3 períodos trimestrales del año activo (2025).
// Datos reales del calendario escolar peruano.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";

export async function seedPeriodoTrimestral() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding periodo_trimestral...");

    // Obtener el ID del año 2025
    const { rows } = await client.query(
      `SELECT id FROM ano_escolar WHERE nombre = '2025'`
    );
    const anoId = rows[0].id;

    await client.query(`
      INSERT INTO periodo_trimestral (ano_escolar_id, numero, fecha_inicio, fecha_fin) VALUES
      ($1, 1, '2025-03-10', '2025-05-30'),
      ($1, 2, '2025-06-09', '2025-08-29'),
      ($1, 3, '2025-09-08', '2025-12-19')
    `, [anoId]);

    console.log("✅ 3 períodos trimestrales insertados (año 2025)");
  } catch (error) {
    console.error("❌ Error seeding periodo_trimestral:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedPeriodoTrimestral().then(() => process.exit(0)).catch(() => process.exit(1));
}
