// ═══════════════════════════════════════════════════════════════
// horario_clase.seed.ts
// ESTE ES EL SEEDER MÁS COMPLEJO porque debe respetar 2 restricciones:
//   1. Una sección no puede tener dos clases al mismo tiempo.
//   2. Un docente no puede estar en dos secciones al mismo tiempo.
//
// Estrategia: asignar bloques horarios fijos y distribuir
// docentes y cursos sin colisiones.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedHorarioClase() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding horarios de clase...");

    const { rows: secciones } = await client.query(
      `SELECT s.id FROM seccion s
       JOIN ano_escolar a ON a.id = s.ano_escolar_id
       WHERE a.nombre = '2025'`
    );

    const { rows: docentes } = await client.query(`SELECT id FROM docente`);
    const { rows: cursos   } = await client.query(`SELECT id, codigo FROM curso`);

    if (docentes.length === 0) throw new Error("No hay docentes.");

    // Bloques horarios disponibles (formato peruano: 7:45 a 12:45)
    const bloques: Array<[string, string]> = [
      ['07:45', '08:30'],
      ['08:30', '09:15'],
      ['09:15', '10:00'],
      ['10:15', '11:00'], // recreo 10:00-10:15
      ['11:00', '11:45'],
      ['11:45', '12:30'],
    ];

    const dias: Array<string> = ['lunes','martes','miercoles','jueves','viernes'];

    // Tracking de colisiones
    // key: "docente_id|dia|hora_inicio"
    // key: "seccion_id|dia|hora_inicio"
    const ocupadoDocente  = new Set<string>();
    const ocupadoSeccion  = new Set<string>();
    // key: "seccion_id" — para el índice parcial de tutoría
    const tieneTutoria    = new Set<number>();

    let insertados = 0;

    // El curso de Tutoría tiene código 'TUT'
    const cursoTutoria = cursos.find(c => c.codigo === 'TUT');

    for (const sec of secciones) {
      // Mezclar días y bloques para mayor variedad
      const diasMezclados = faker.helpers.shuffle([...dias]);

      for (const dia of diasMezclados) {
        const bloquesMezclados = faker.helpers.shuffle([...bloques]);

        for (const [hi, hf] of bloquesMezclados) {
          const keySeccion = `${sec.id}|${dia}|${hi}`;
          if (ocupadoSeccion.has(keySeccion)) continue; // La sección ya tiene clase aquí

          // Elegir docente disponible en ese día/hora
          const docentesDisponibles = docentes.filter(d => {
            const keyDoc = `${d.id}|${dia}|${hi}`;
            return !ocupadoDocente.has(keyDoc);
          });

          if (docentesDisponibles.length === 0) continue; // No hay docente libre

          const docente  = faker.helpers.arrayElement(docentesDisponibles);

          // Decidir si es tutoría (solo si la sección no tiene tutoría aún)
          const esTutoria = cursoTutoria &&
                            !tieneTutoria.has(sec.id) &&
                            faker.datatype.boolean({ probability: 0.15 });

          const curso = esTutoria
            ? cursoTutoria
            : faker.helpers.arrayElement(cursos.filter(c => c.codigo !== 'TUT'));

          // Marcar como ocupado
          ocupadoSeccion.add(keySeccion);
          ocupadoDocente.add(`${docente.id}|${dia}|${hi}`);
          if (esTutoria) tieneTutoria.add(sec.id);

          await client.query(
            `INSERT INTO horario_clase
               (seccion_id, curso_id, docente_id, dia_semana, hora_inicio, hora_fin, es_tutoria)
             VALUES ($1,$2,$3,$4,$5,$6,$7)
             ON CONFLICT DO NOTHING`,
            [sec.id, curso.id, docente.id, dia, hi, hf, esTutoria ?? false]
          );
          insertados++;
        }
      }
    }

    console.log(`✅ ${insertados} bloques de horario insertados`);
  } catch (error) {
    console.error("❌ Error seeding horario_clase:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedHorarioClase().then(() => process.exit(0)).catch(() => process.exit(1));
}
