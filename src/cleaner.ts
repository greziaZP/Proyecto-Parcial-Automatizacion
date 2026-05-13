// cleaner.ts
// Elimina todas las tablas del esquema en orden inverso a las FK.
// Usar DROP SCHEMA ... CASCADE es la forma más limpia en PostgreSQL:
// elimina todo el esquema y su contenido en un solo comando.
// Se recrea vacío para el siguiente seed:schema.

import { pool } from "./config";

async function cleanDatabase() {
  const client = await pool.connect();
  try {
    console.log("🧹 Limpiando base de datos...");
    await client.query(`DROP SCHEMA public CASCADE`);
    await client.query(`CREATE SCHEMA public`);
    console.log("✅ Base de datos limpia y lista.");
  } catch (error) {
    console.error("❌ Error limpiando la base de datos:", error);
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

cleanDatabase()
  .then(() => process.exit(0))
  .catch(() => process.exit(1));
