// config.ts
// Configuración del pool de conexión a PostgreSQL.
// Se usa pg (node-postgres) en lugar de mysql2 porque nuestro esquema es PostgreSQL.
// Pool: mantiene múltiples conexiones abiertas para reutilizarlas — más eficiente
// que abrir y cerrar una conexión por cada query.

import { Pool } from "pg";
import * as dotenv from "dotenv";
dotenv.config({ path: ".env" });

export const pool = new Pool({
  host:     process.env.PG_HOST     || "localhost",
  port:     Number(process.env.PG_PORT) || 5432,
  user:     process.env.PG_USER     || "postgres",
  password: process.env.PG_PASSWORD || "",
  database: process.env.PG_DATABASE || "asistencia_colegio",
});

// Función helper para ejecutar queries con el pool
// Usamos pool.query() directamente (no pool.connect()) para queries simples.
// Para seeders con múltiples inserts relacionados usamos un client para
// poder hacer rollback si algo falla en medio del proceso.
export async function getClient() {
  const client = await pool.connect();
  return client;
}
