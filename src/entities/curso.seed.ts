// ═══════════════════════════════════════════════════════════════
// curso.seed.ts
// Catálogo de materias reales del currículo nacional peruano.
// Son datos fijos — no usa Faker porque son materias reales.
// ═══════════════════════════════════════════════════════════════
import { pool } from "../config";

export async function seedCurso() {
  const client = await pool.connect();
  try {
    console.log("🌱 Seeding cursos...");

    const cursos = [
      ['Comunicación',                          'COM'],
      ['Matemática',                            'MAT'],
      ['Inglés',                                'ING'],
      ['Historia, Geografía y Economía',        'HGE'],
      ['Formación Ciudadana y Cívica',          'FCC'],
      ['Persona, Familia y Relaciones Humanas', 'PFRH'],
      ['Educación para el Trabajo',             'EPT'],
      ['Ciencia, Tecnología y Ambiente',        'CTA'],
      ['Arte y Cultura',                        'ART'],
      ['Educación Física',                      'EDF'],
      ['Educación Religiosa',                   'REL'],
      ['Tutoría',                               'TUT'],
    ];

    for (const [nombre, codigo] of cursos) {
      await client.query(
        `INSERT INTO curso (nombre, codigo) VALUES ($1, $2)`,
        [nombre, codigo]
      );
    }

    console.log(`✅ ${cursos.length} cursos insertados`);
  } catch (error) {
    console.error("❌ Error seeding curso:", error);
    throw error;
  } finally {
    client.release();
  }
}

if (require.main === module) {
  seedCurso().then(() => process.exit(0)).catch(() => process.exit(1));
}
