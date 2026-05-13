// ═══════════════════════════════════════════════════════════════
// docente.seed.ts
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

const especialidades = [
  'Matemática', 'Comunicación', 'Inglés', 'Historia', 'Ciencias',
  'Educación Física', 'Arte', 'Religión', 'Computación', 'Formación Ciudadana',
];

export async function seedDocente() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding docentes...");

    const { rows } = await client.query(
      `SELECT id FROM usuario
       WHERE rol = 'docente'
       AND id NOT IN (SELECT usuario_id FROM docente)`
    );

    for (const u of rows) {
      const especialidad = faker.helpers.arrayElement(especialidades);
      await client.query(
        `INSERT INTO docente (usuario_id, especialidad) VALUES ($1,$2)`,
        [u.id, especialidad]
      );
    }

    console.log(`✅ ${rows.length} docentes insertados`);
  } catch (error) {
    console.error("❌ Error seeding docente:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedDocente().then(() => process.exit(0)).catch(() => process.exit(1));
}
