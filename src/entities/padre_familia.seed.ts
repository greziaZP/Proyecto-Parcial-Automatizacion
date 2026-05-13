// ═══════════════════════════════════════════════════════════════
// padre_familia.seed.ts
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedPadreFamilia() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding padres de familia...");

    const { rows } = await client.query(
      `SELECT id FROM usuario
       WHERE rol = 'padre'
       AND id NOT IN (SELECT usuario_id FROM padre_familia)`
    );

    const dniUsados = new Set<string>();

    for (const u of rows) {
      let dni: string;
      do {
        dni = faker.number.int({ min: 10000000, max: 99999999 }).toString();
      } while (dniUsados.has(dni));
      dniUsados.add(dni);

      const telefono = `+51 9${faker.string.numeric(8)}`;

      await client.query(
        `INSERT INTO padre_familia (usuario_id, dni, telefono) VALUES ($1,$2,$3)`,
        [u.id, dni, telefono]
      );
    }

    console.log(`✅ ${rows.length} padres de familia insertados`);
  } catch (error) {
    console.error("❌ Error seeding padre_familia:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedPadreFamilia().then(() => process.exit(0)).catch(() => process.exit(1));
}
