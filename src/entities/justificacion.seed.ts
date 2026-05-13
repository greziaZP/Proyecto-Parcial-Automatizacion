// ═══════════════════════════════════════════════════════════════
// justificacion.seed.ts
// Genera ~40 justificaciones distribuidas entre los tipos del proceso:
//   - retiro_apoderado      → padre presenta documento al día siguiente
//   - certificado_medico    → el más común
//   - actividad_institucional → olimpiadas, deporte, visitas
//   - permiso_direccion     → autorización directa del colegio
// Algunas están aprobadas, otras pendientes, pocas rechazadas.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";
import { faker } from "@faker-js/faker";

const DESCRIPCIONES: Record<string, string[]> = {
  retiro_apoderado: [
    'Apoderado retiró al alumno por cita médica urgente',
    'Retiro anticipado por trámite familiar',
    'Apoderado retiró al alumno por emergencia familiar',
  ],
  certificado_medico: [
    'Certificado médico por faringitis aguda',
    'Reposo médico por gastroenteritis',
    'Certificado por control pediátrico de rutina',
    'Reposo por esguince — presentado al día siguiente',
    'Certificado por fiebre alta',
  ],
  actividad_institucional: [
    'Participación en Olimpiada Matemática Regional',
    'Representación del colegio en Juegos Deportivos',
    'Visita académica al Museo de la Nación',
    'Ensayo general para acto cívico del colegio',
    'Competencia de oratoria interescolar',
  ],
  permiso_direccion: [
    'Autorización de Dirección por viaje familiar programado',
    'Permiso de Dirección para evento deportivo fuera de Lima',
    'Autorización institucional por actividad extracurricular',
  ],
};

export async function seedJustificacion() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding justificaciones...");

    // Necesitamos matrículas con apoderado vinculado (para presentado_por)
    const { rows: matriculasConPadre } = await client.query(`
      SELECT m.id AS matricula_id, rpe.padre_id
      FROM matricula m
      JOIN estudiante e    ON e.id = m.estudiante_id
      JOIN relacion_padre_estudiante rpe
        ON rpe.estudiante_id = e.id AND rpe.es_apoderado_principal = TRUE
      WHERE m.estado = 'activa'
    `);

    const { rows: admins } = await client.query(
      `SELECT id FROM usuario WHERE rol IN ('admin','auxiliar')`
    );

    if (matriculasConPadre.length === 0) throw new Error("No hay matrículas con apoderado.");

    const tipos = Object.keys(DESCRIPCIONES) as Array<keyof typeof DESCRIPCIONES>;
    const estados = ['aprobada','aprobada','aprobada','pendiente','rechazada'] as const;
    // 60% aprobada, 20% pendiente, 20% rechazada (distribución realista)

    const seleccionados = faker.helpers.arrayElements(
      matriculasConPadre,
      Math.min(40, matriculasConPadre.length)
    );

    let insertados = 0;

    for (const m of seleccionados) {
      const tipo   = faker.helpers.arrayElement(tipos);
      const estado = faker.helpers.arrayElement(estados);

      // Fecha del evento: entre 1 y 50 días atrás
      const daysAgo    = faker.number.int({ min: 1, max: 50 });
      const fechaEvento = new Date();
      fechaEvento.setDate(fechaEvento.getDate() - daysAgo);
      while (fechaEvento.getDay() === 0 || fechaEvento.getDay() === 6)
        fechaEvento.setDate(fechaEvento.getDate() - 1);
      const fechaEventoStr = fechaEvento.toISOString().split('T')[0];

      // Fecha de presentación: mismo día o día siguiente al evento
      const offsetPresentacion = faker.number.int({ min: 0, max: 2 });
      const fechaPresentacion  = new Date(fechaEvento);
      fechaPresentacion.setDate(fechaPresentacion.getDate() + offsetPresentacion);
      const fechaPresentacionStr = fechaPresentacion.toISOString().split('T')[0];

      // actividad_institucional puede no tener padre (la registra la Dirección)
      const presentadoPor = tipo === 'actividad_institucional' && Math.random() < 0.5
        ? null
        : m.padre_id;

      // Solo tiene autorizador si está aprobada o rechazada
      const autorizadoPor = (estado === 'aprobada' || estado === 'rechazada')
        ? faker.helpers.arrayElement(admins).id
        : null;

      // Documento de referencia (solo para certificados médicos y permisos)
      const docRef = (tipo === 'certificado_medico' || tipo === 'permiso_direccion')
        ? `DOC-${faker.string.alphanumeric(8).toUpperCase()}`
        : null;

      const descripcion = faker.helpers.arrayElement(DESCRIPCIONES[tipo]);

      await client.query(`
        INSERT INTO justificacion (
          matricula_id, tipo, estado,
          presentado_por, autorizado_por,
          fecha_presentacion, fecha_inicio_evento, fecha_fin_evento,
          descripcion, documento_referencia
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
      `, [
        m.matricula_id, tipo, estado,
        presentadoPor, autorizadoPor,
        fechaPresentacionStr, fechaEventoStr, fechaEventoStr,
        descripcion, docRef,
      ]);
      insertados++;
    }

    console.log(`✅ ${insertados} justificaciones insertadas`);
  } catch (error) {
    console.error("❌ Error seeding justificacion:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedJustificacion().then(() => process.exit(0)).catch(() => process.exit(1));
}
