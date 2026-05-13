// ═══════════════════════════════════════════════════════════════
// fuga.seed.ts
// Crea un evento fuga por cada asistencia_clase con estado='fuga'.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedFuga() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding fugas...");

    // Obtener asistencias con estado fuga que no tienen fuga aún
    const { rows: asistenciasFuga } = await client.query(
      `SELECT ac.id, ac.registrado_por, ac.fecha
       FROM asistencia_clase ac
       LEFT JOIN fuga f ON f.asistencia_clase_id = ac.id
       WHERE ac.estado = 'fuga' AND f.id IS NULL`
    );

    const { rows: usuarios } = await client.query(
      `SELECT id FROM usuario WHERE rol IN ('auxiliar','admin')`
    );

    const canalesAviso = ['verbal','app','sms','whatsapp'] as const;
    const estadosFuga  = ['pendiente','ubicado','no_ubicado'] as const;
    let insertados = 0;

    for (const ac of asistenciasFuga) {
      const estado     = faker.helpers.arrayElement(estadosFuga);
      const canal      = faker.helpers.arrayElement(canalesAviso);
      const resueltoPor = estado !== 'pendiente'
        ? faker.helpers.arrayElement(usuarios)?.id ?? null
        : null;
      const resueltoEn = estado !== 'pendiente'
        ? (() => {
            const fecha = typeof ac.fecha === 'string' 
              ? ac.fecha 
              : new Date(ac.fecha).toISOString().split('T')[0];
            const hora = faker.number.int({min:8,max:12});
            const min = String(faker.number.int({min:0,max:59})).padStart(2,'0');
            return `${fecha}T${hora}:${min}:00-05:00`;
          })()
        : null;

      await client.query(
        `INSERT INTO fuga
           (asistencia_clase_id, reportado_por, estado, canal_aviso, resuelto_por, resuelto_en)
         VALUES ($1,$2,$3,$4,$5,$6)
         ON CONFLICT DO NOTHING`,
        [ac.id, ac.registrado_por, estado, canal, resueltoPor, resueltoEn]
      );
      insertados++;
    }

    console.log(`✅ ${insertados} fugas insertadas`);
  } catch (error) {
    console.error("❌ Error seeding fuga:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedFuga().then(() => process.exit(0)).catch(() => process.exit(1));
}
