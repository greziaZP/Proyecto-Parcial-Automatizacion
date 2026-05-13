// ═══════════════════════════════════════════════════════════════
// ano_escolar.seed.ts
// Inserta el año escolar activo. Es catálogo — pocos registros fijos.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";

export async function seedAnoEscolar() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding ano_escolar...");
    await client.query(`
      INSERT INTO ano_escolar (nombre, fecha_inicio, fecha_fin, activo) VALUES
      ('2025', '2025-03-10', '2025-12-19', TRUE),
      ('2024', '2024-03-11', '2024-12-20', FALSE)
    `);
    console.log("✅ 2 años escolares insertados (2025 activo, 2024 histórico)");
  } catch (error) {
    console.error("❌ Error seeding ano_escolar:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedAnoEscolar().then(() => process.exit(0)).catch(() => process.exit(1));
}
