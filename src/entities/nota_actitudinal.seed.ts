// ═══════════════════════════════════════════════════════════════
// nota_actitudinal.seed.ts
// Calcula y cierra la nota actitudinal por alumno por período.
//
// REGLA DE NEGOCIO CRÍTICA:
//   Los registros con estado='justificado' NO penalizan.
//   La fórmula es: MAX(0, 20 - (tard×0.5) - (inas×1.0) - (fugas×1.5))
//
// Este seeder simula el cierre que hace Registro Técnico al final
// de cada período. Solo cierra períodos cuya fecha_fin ya pasó.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

export async function seedNotaActitudinal() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding notas actitudinales...");

    // Períodos cuya fecha_fin ya pasó (podemos calcular nota)
    const { rows: periodos } = await client.query(`
      SELECT pt.id, pt.fecha_inicio, pt.fecha_fin
      FROM periodo_trimestral pt
      WHERE pt.fecha_fin <= CURRENT_DATE
    `);

    if (periodos.length === 0) {
      console.log("⚠️  No hay períodos cerrados aún. Insertando datos de prueba igualmente...");
      // Si no hay períodos cerrados aún (año en curso) igualmente generamos
      // notas para todos los períodos como si ya cerraran — datos de prueba
    }

    // Usar todos los períodos para los datos de prueba
    const { rows: todosPeriodos } = await client.query(
      `SELECT id, fecha_inicio, fecha_fin FROM periodo_trimestral`
    );

    const { rows: matriculas } = await client.query(
      `SELECT id FROM matricula WHERE estado = 'activa'`
    );

    const { rows: admins } = await client.query(
      `SELECT id FROM usuario WHERE rol IN ('admin','auxiliar') LIMIT 1`
    );
    const adminId = admins[0]?.id ?? null;

    let insertados = 0;

    for (const periodo of todosPeriodos) {
      for (const mat of matriculas) {

        // Contar tardanzas del período (excluyendo justificadas)
        const { rows: tardanzas } = await client.query(`
          SELECT COUNT(*) AS total
          FROM registro_ingreso
          WHERE matricula_id = $1
            AND fecha BETWEEN $2 AND $3
            AND estado = 'tardanza'
        `, [mat.id, periodo.fecha_inicio, periodo.fecha_fin]);

        // Contar inasistencias del período (excluyendo justificadas)
        const { rows: inasistencias } = await client.query(`
          SELECT COUNT(*) AS total
          FROM registro_ingreso
          WHERE matricula_id = $1
            AND fecha BETWEEN $2 AND $3
            AND estado = 'inasistencia'
        `, [mat.id, periodo.fecha_inicio, periodo.fecha_fin]);

        // Contar fugas NO justificadas del período
        const { rows: fugas } = await client.query(`
          SELECT COUNT(*) AS total
          FROM fuga f
          JOIN asistencia_clase ac ON ac.id = f.asistencia_clase_id
          WHERE ac.matricula_id = $1
            AND ac.fecha BETWEEN $2 AND $3
            AND f.estado IN ('ubicado','no_ubicado')
        `, [mat.id, periodo.fecha_inicio, periodo.fecha_fin]);

        const totalTardanzas     = parseInt(tardanzas[0].total);
        const totalInasistencias = parseInt(inasistencias[0].total);
        const totalFugas         = parseInt(fugas[0].total);

        // Fórmula: MAX(0, 20 - tard×0.5 - inas×1.0 - fugas×1.5)
        const valor = Math.max(
          0,
          20 - (totalTardanzas * 0.5) - (totalInasistencias * 1.0) - (totalFugas * 1.5)
        );

        // Promedio académico: dato externo simulado (entre 10 y 20 en escala peruana)
        const promedioAcademico = parseFloat(
          (faker.number.float({ min: 10, max: 20, fractionDigits: 2 })).toFixed(2)
        );

        // Estado: los períodos pasados están 'entregados', el actual 'publicado'
        const hoy    = new Date();
        const finPer = new Date(periodo.fecha_fin);
        const estado = finPer < hoy ? 'entregado' : 'publicado';

        await client.query(`
          INSERT INTO nota_actitudinal (
            matricula_id, periodo_id,
            total_tardanzas, total_inasistencias, total_fugas,
            valor, promedio_academico, estado_reporte, generado_por
          ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
          ON CONFLICT (matricula_id, periodo_id) DO UPDATE
            SET total_tardanzas     = EXCLUDED.total_tardanzas,
                total_inasistencias = EXCLUDED.total_inasistencias,
                total_fugas         = EXCLUDED.total_fugas,
                valor               = EXCLUDED.valor,
                promedio_academico  = EXCLUDED.promedio_academico,
                calculado_en        = NOW()
        `, [
          mat.id, periodo.id,
          totalTardanzas, totalInasistencias, totalFugas,
          valor.toFixed(2), promedioAcademico, estado, adminId,
        ]);
        insertados++;
      }
    }

    console.log(`✅ ${insertados} notas actitudinales insertadas/actualizadas`);
    console.log(`   • ${todosPeriodos.length} períodos × ${matriculas.length} alumnos`);
  } catch (error) {
    console.error("❌ Error seeding nota_actitudinal:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedNotaActitudinal().then(() => process.exit(0)).catch(() => process.exit(1));
}
