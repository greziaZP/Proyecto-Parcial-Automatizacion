// ═══════════════════════════════════════════════════════════════
// relacion_padre_estudiante.seed.ts
// Vincula padres con estudiantes. Cada estudiante tiene al menos 1 padre.
// Algunos estudiantes tienen 2 apoderados (padre + madre).
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedRelacionPadreEstudiante() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding relaciones padre-estudiante...");

    const { rows: padres }     = await client.query(`SELECT id FROM padre_familia`);
    const { rows: estudiantes } = await client.query(`SELECT id FROM estudiante`);

    if (padres.length === 0 || estudiantes.length === 0) {
      throw new Error("No hay padres o estudiantes para vincular.");
    }

    let insertados = 0;
    const vinculos = new Set<string>(); // Evitar duplicados (padre_id, estudiante_id)

    // Garantizar que cada estudiante tenga al menos 1 apoderado
    for (const est of estudiantes) {
      const padre = faker.helpers.arrayElement(padres);
      const key   = `${padre.id}-${est.id}`;

      if (!vinculos.has(key)) {
        vinculos.add(key);
        await client.query(
          `INSERT INTO relacion_padre_estudiante
             (padre_id, estudiante_id, parentesco, es_apoderado_principal)
           VALUES ($1,$2,$3,TRUE)`,
          [padre.id, est.id, 'padre']
        );
        insertados++;
      }

      // 40% de probabilidad de tener un segundo apoderado (la madre)
      if (faker.datatype.boolean({ probability: 0.4 })) {
        const otroPadre = faker.helpers.arrayElement(padres);
        const key2 = `${otroPadre.id}-${est.id}`;
        if (!vinculos.has(key2) && otroPadre.id !== padre.id) {
          vinculos.add(key2);
          await client.query(
            `INSERT INTO relacion_padre_estudiante
               (padre_id, estudiante_id, parentesco, es_apoderado_principal)
             VALUES ($1,$2,$3,FALSE)`,
            [otroPadre.id, est.id, 'madre']
          );
          insertados++;
        }
      }
    }

    console.log(`✅ ${insertados} vínculos padre-estudiante insertados`);
  } catch (error) {
    console.error("❌ Error seeding relacion_padre_estudiante:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedRelacionPadreEstudiante().then(() => process.exit(0)).catch(() => process.exit(1));
}
