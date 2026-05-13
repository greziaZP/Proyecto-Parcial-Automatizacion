// ═══════════════════════════════════════════════════════════════
// estudiante.seed.ts
// Crea registros de estudiante para todos los usuarios con rol='estudiante'.
// PATRÓN CLAVE: siempre leer los IDs de la BD en lugar de asumir rangos.
// Así el seeder funciona sin importar el orden de inserción de usuarios.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedEstudiante() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding estudiantes...");

    // Obtener usuarios con rol estudiante que aún no tienen subtype
    const { rows: usuariosEst } = await client.query(
      `SELECT id FROM usuario
       WHERE rol = 'estudiante'
       AND id NOT IN (SELECT usuario_id FROM estudiante)`
    );

    const dniUsados = new Set<string>();

    for (const u of usuariosEst) {
      // Generar DNI único de 8 dígitos (formato peruano)
      let dni: string;
      do {
        dni = faker.number.int({ min: 10000000, max: 99999999 }).toString();
      } while (dniUsados.has(dni));
      dniUsados.add(dni);

      // Edad entre 11 y 17 años (secundaria peruana)
      const fechaNac = faker.date.birthdate({ min: 11, max: 17, mode: 'age' });

      await client.query(
        `INSERT INTO estudiante (usuario_id, dni, fecha_nacimiento) VALUES ($1,$2,$3)`,
        [u.id, dni, fechaNac]
      );
    }

    console.log(`✅ ${usuariosEst.length} estudiantes insertados`);
  } catch (error) {
    console.error("❌ Error seeding estudiante:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedEstudiante().then(() => process.exit(0)).catch(() => process.exit(1));
}
