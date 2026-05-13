import { Pool } from "pg";
import * as dotenv from "dotenv";
dotenv.config({ path: ".env" });

const pool = new Pool({
  host:     process.env.PG_HOST,
  port:     Number(process.env.PG_PORT),
  user:     process.env.PG_USER,
  password: process.env.PG_PASSWORD,
  database: process.env.PG_DATABASE,
  connectionTimeoutMillis: 10000,
});

async function test() {
  console.log("Conectando a:", process.env.PG_HOST);
  console.log("Usuario:", process.env.PG_USER);
  try {
    const client = await pool.connect();
    const res = await client.query("SELECT version()");
    console.log("✅ CONECTADO:", res.rows[0].version);
    client.release();
  } catch (err) {
    console.error("❌ ERROR:", err.message);
  } finally {
    await pool.end();
  }
}
test();
