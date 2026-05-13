// ═══════════════════════════════════════════════════════════════
// registro_ingreso.seed.ts
// Genera el control matutino del Auxiliar para los últimos 60 días hábiles.
// Distribución realista:
//   - 85% presente
//   - 8%  tardanza
//   - 7%  inasistencia
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

// Genera los últimos N días hábiles (lunes a viernes) sin feriados
function diasHabiles(cantidad: number): Date[] {
  const dias: Date[] = [];
  const hoy = new Date();
  let cursor = new Date(hoy);

  while (dias.length < cantidad) {
    cursor.setDate(cursor.getDate() - 1);
    const diaSemana = cursor.getDay(); // 0=dom, 6=sab
    if (diaSemana >= 1 && diaSemana <= 5) {
      dias.push(new Date(cursor));
    }
  }
  return dias.reverse(); // Del más antiguo al más reciente
}

export async function seedRegistroIngreso() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding registros de ingreso...");

    // Obtener el auxiliar
    const { rows: auxiliares } = await client.query(
      `SELECT id FROM usuario WHERE rol = 'auxiliar' LIMIT 1`
    );
    if (auxiliares.length === 0) throw new Error("No hay auxiliar registrado.");
    const auxiliarId = auxiliares[0].id;

    // Obtener todas las matrículas activas
    const { rows: matriculas } = await client.query(
      `SELECT id FROM matricula WHERE estado = 'activa'`
    );

    const fechas = diasHabiles(60); // 60 días hábiles ~ 3 meses
    let insertados = 0;
    const BATCH_SIZE = 1000;
    let batch: Array<[number, number, string, string | null, string]> = [];

    for (const fecha of fechas) {
      const fechaStr = fecha.toISOString().split('T')[0];

      for (const mat of matriculas) {
        // Distribución realista de estados
        const rand = Math.random();
        let estado: string;
        let horaLlegada: string | null;

        if (rand < 0.85) {
          estado = 'presente';
          // Llegada entre 7:25 y 7:30
          const minutos = faker.number.int({ min: 25, max: 30 });
          horaLlegada = `${fechaStr}T07:${String(minutos).padStart(2,'0')}:00-05:00`;
        } else if (rand < 0.93) {
          estado = 'tardanza';
          // Llegada entre 7:31 y 8:15
          const hora  = Math.random() < 0.7 ? 7 : 8;
          const minuto = hora === 7
            ? faker.number.int({ min: 31, max: 59 })
            : faker.number.int({ min: 0,  max: 15 });
          horaLlegada = `${fechaStr}T0${hora}:${String(minuto).padStart(2,'0')}:00-05:00`;
        } else {
          estado = 'inasistencia';
          horaLlegada = null;
        }

        batch.push([mat.id, auxiliarId, fechaStr, horaLlegada, estado]);
        insertados++;

        // Ejecutar batch insert cada 1000 registros
        if (batch.length >= BATCH_SIZE) {
          await batchInsertRegistroIngreso(client, batch);
          batch = [];
        }
      }
    }

    // Insertar los registros restantes
    if (batch.length > 0) {
      await batchInsertRegistroIngreso(client, batch);
    }

    console.log(`✅ ${insertados} registros de ingreso insertados`);
    console.log(`   • ${fechas.length} días hábiles × ${matriculas.length} alumnos`);
  } catch (error) {
    console.error("❌ Error seeding registro_ingreso:", error);
    throw error;
  } finally {
    client.release();
  }
}

async function batchInsertRegistroIngreso(
  client: any,
  batch: Array<[number, number, string, string | null, string]>
): Promise<void> {
  if (batch.length === 0) return;

  const values = batch
    .map((_, i) => `($${i * 5 + 1},$${i * 5 + 2},$${i * 5 + 3},$${i * 5 + 4},$${i * 5 + 5})`)
    .join(',');

  const params = batch.flat();

  await client.query(
    `INSERT INTO registro_ingreso
       (matricula_id, auxiliar_id, fecha, hora_llegada, estado)
     VALUES ${values}
     ON CONFLICT DO NOTHING`,
    params
  );
}

if (require.main === module) {
  seedRegistroIngreso().then(() => process.exit(0)).catch(() => process.exit(1));
}
