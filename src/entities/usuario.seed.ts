// ═══════════════════════════════════════════════════════════════
// usuario.seed.ts
// PATRÓN "2 SOMOS NOSOTROS":
//   - Los 2 primeros registros son los integrantes del equipo (datos reales).
//   - El resto son generados con Faker.
// Distribución de roles:
//   - 2  admin/equipo  (hardcodeados)
//   - 1  auxiliar      (el auxiliar de piso del proceso)
//   - 15 docentes      (uno por horario de clase aprox.)
//   - 80 estudiantes   (alumnos del colegio)
//   - 15 padres        (apoderados)
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";
import * as bcrypt from "bcrypt"; // Opcional: si no tienen bcrypt, usar hash fijo

// Hash fijo para todos los usuarios de prueba (contraseña: "password123")
// En un proyecto real se hashearía con bcrypt.
const DEFAULT_HASH = "$2b$10$fixedHashForTestingPurposesOnly123456789";

export async function seedUsuario() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding usuarios...");

    const usuarios: Array<[string, string, string, string, string]> = [];

    // ── LOS 2 REALES (hardcodeados) ─────────────────────────────
    // ⚠️ CAMBIA ESTOS DATOS por los nombres reales del equipo
    usuarios.push(
      ['Eduardo',         'Mamani',         'emamania1@upao.edu.pe',   'admin',    DEFAULT_HASH],
      ['Grezia',  'Merino',  'gmerinop1@upao.edu.pe', 'admin',    DEFAULT_HASH],
    );

    // ── 1 AUXILIAR ───────────────────────────────────────────────
    usuarios.push([
      faker.person.firstName(),
      faker.person.lastName(),
      faker.internet.email(),
      'auxiliar',
      DEFAULT_HASH,
    ]);

    // ── 15 DOCENTES ──────────────────────────────────────────────
    for (let i = 0; i < 15; i++) {
      usuarios.push([
        faker.person.firstName(),
        faker.person.lastName(),
        faker.internet.email(),
        'docente',
        DEFAULT_HASH,
      ]);
    }

    // ── 80 ESTUDIANTES ───────────────────────────────────────────
    for (let i = 0; i < 80; i++) {
      usuarios.push([
        faker.person.firstName(),
        faker.person.lastName(),
        faker.internet.email(),
        'estudiante',
        DEFAULT_HASH,
      ]);
    }

    // ── 15 PADRES ────────────────────────────────────────────────
    for (let i = 0; i < 15; i++) {
      usuarios.push([
        faker.person.firstName(),
        faker.person.lastName(),
        faker.internet.email(),
        'padre',
        DEFAULT_HASH,
      ]);
    }

    // Insertar todos en lote
    for (const [nombres, apellidos, email, rol, hash] of usuarios) {
      await client.query(
        `INSERT INTO usuario (nombres, apellidos, email, rol, password_hash)
         VALUES ($1,$2,$3,$4,$5)`,
        [nombres, apellidos, email, rol, hash]
      );
    }

    console.log(`✅ ${usuarios.length} usuarios insertados`);
    console.log(`   • 2 reales (equipo)`);
    console.log(`   • 1 auxiliar`);
    console.log(`   • 15 docentes`);
    console.log(`   • 80 estudiantes`);
    console.log(`   • 15 padres`);
  } catch (error) {
    console.error("❌ Error seeding usuario:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedUsuario().then(() => process.exit(0)).catch(() => process.exit(1));
}
