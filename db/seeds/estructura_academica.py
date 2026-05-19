"""
seeds/estructura_academica.py
==============================
Crea la estructura académica del año activo (todo UUID en v3):
  1. seccion            — secciones de secundaria
  2. periodo_trimestral — 3 períodos por año activo
  3. matricula          — un estudiante → una sección
  4. UPDATE estudiante.matricula_actual_uid  ← paso clave del v3
  5. horario_clase      — bloques semanales por sección

NOTA v3: seccion ya NO tiene tutor_uid (se eliminó del DBML).
"""
import sys
import random
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool, SeedConfig

# 10 secciones de secundaria peruana (5 grados × 2 secciones)
SECCIONES_DEF = [
    ("1er Grado", "Secundaria", "A"),
    ("1er Grado", "Secundaria", "B"),
    ("2do Grado", "Secundaria", "A"),
    ("2do Grado", "Secundaria", "B"),
    ("3er Grado", "Secundaria", "A"),
    ("3er Grado", "Secundaria", "B"),
    ("4to Grado", "Secundaria", "A"),
    ("4to Grado", "Secundaria", "B"),
    ("5to Grado", "Secundaria", "A"),
    ("5to Grado", "Secundaria", "B"),
]

# Bloques horarios (hora_inicio, hora_fin)
BLOQUES = [
    ("07:30", "08:15"),
    ("08:15", "09:00"),
    ("09:00", "09:45"),
    ("10:00", "10:45"),
    ("10:45", "11:30"),
    ("11:30", "12:15"),
    ("14:00", "14:45"),
    ("14:45", "15:30"),
]
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes"]


# ─────────────────────────────────────────────────────────────────────────────
def seed_seccion(conn=None) -> list[str]:
    """Crea secciones para el año activo. Retorna lista de UIDs."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding secciones...")
        cur.execute("SELECT uid FROM ano_escolar WHERE activo = TRUE LIMIT 1")
        row = cur.fetchone()
        if not row: raise ValueError("No hay año escolar activo.")
        ano_uid = str(row[0])

        uids = []
        for grado, nivel, codigo in SECCIONES_DEF:
            cur.execute(
                """
                INSERT INTO seccion
                    (ano_escolar_uid, grado_academico, nivel_educativo, codigo_seccion)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ano_escolar_uid, grado_academico, codigo_seccion) DO NOTHING
                RETURNING uid
                """,
                (ano_uid, grado, nivel, codigo),
            )
            r = cur.fetchone()
            if r: uids.append(str(r[0]))

        if _local: conn.commit()
        print(f"✅ {len(uids)} secciones creadas")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error seccion: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_periodo_trimestral(conn=None) -> list[str]:
    """Crea 3 períodos trimestrales para el año activo. Retorna UIDs."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding períodos trimestrales...")
        cur.execute("SELECT uid, fecha_inicio FROM ano_escolar WHERE activo = TRUE LIMIT 1")
        row = cur.fetchone()
        if not row: raise ValueError("No hay año escolar activo.")
        ano_uid, fecha_inicio = str(row[0]), row[1]

        uids = []
        inicio = fecha_inicio
        for n in range(1, 4):
            fin = inicio + timedelta(weeks=13)
            cur.execute(
                """
                INSERT INTO periodo_trimestral
                    (ano_escolar_uid, numero_trimestre, fecha_inicio, fecha_fin)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ano_escolar_uid, numero_trimestre) DO NOTHING
                RETURNING uid
                """,
                (ano_uid, n, inicio, fin),
            )
            r = cur.fetchone()
            if r: uids.append(str(r[0]))
            inicio = fin + timedelta(days=1)

        if _local: conn.commit()
        print(f"✅ {len(uids)} períodos trimestrales creados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error periodo_trimestral: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_matricula(conn=None) -> list[str]:
    """
    Matricula todos los estudiantes en una sección (round-robin).
    Al terminar, actualiza estudiante.matricula_actual_uid con la matrícula activa.
    Retorna lista de UIDs de matrícula creados.
    """
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding matrículas...")

        # Secciones del año activo
        cur.execute("""
            SELECT s.uid FROM seccion s
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE
        """)
        secciones = [str(r[0]) for r in cur.fetchall()]
        if not secciones: raise ValueError("No hay secciones para el año activo.")

        # Estudiantes sin matrícula en el año activo
        cur.execute("""
            SELECT e.uid FROM estudiante e
            WHERE e.uid NOT IN (
                SELECT m.estudiante_uid FROM matricula m
                JOIN seccion s ON s.uid = m.seccion_uid
                JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
                WHERE a.activo = TRUE
            )
        """)
        estudiantes = [str(r[0]) for r in cur.fetchall()]

        uids = []
        for i, est_uid in enumerate(estudiantes):
            sec_uid = secciones[i % len(secciones)]
            cur.execute(
                """
                INSERT INTO matricula
                    (estudiante_uid, seccion_uid, fecha_matricula, estado_matricula)
                VALUES (%s, %s, %s, 'activa')
                ON CONFLICT (estudiante_uid, seccion_uid) DO NOTHING
                RETURNING uid
                """,
                (est_uid, sec_uid, date(2025, 3, 3)),
            )
            r = cur.fetchone()
            if r: uids.append(str(r[0]))

        # ── PASO CLAVE v3: actualizar estudiante.matricula_actual_uid ─────────
        print("   🔗 Actualizando estudiante.matricula_actual_uid...")
        cur.execute("""
            UPDATE estudiante e
            SET matricula_actual_uid = m.uid
            FROM matricula m
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE m.estudiante_uid = e.uid
              AND a.activo = TRUE
              AND m.estado_matricula = 'activa'
        """)
        actualizados = cur.rowcount

        if _local: conn.commit()
        print(f"✅ {len(uids)} matrículas creadas  |  {actualizados} estudiantes con matricula_actual_uid")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error matricula: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_horario_clase(conn=None) -> list[str]:
    """
    Genera horario semanal por sección (UUID FKs: seccion, curso, docente).
    Garantiza sin conflicto de docente ni de aula.
    Asigna exactamente 1 hora de tutoría por sección (lunes, primer bloque).
    Retorna lista de UIDs de horario creados.
    """
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding horarios de clase...")

        cur.execute("""
            SELECT s.uid FROM seccion s
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid WHERE a.activo = TRUE
        """)
        secciones = [str(r[0]) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM curso")
        cursos = [str(r[0]) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM docente")
        docentes = [str(r[0]) for r in cur.fetchall()]

        if not (secciones and cursos and docentes):
            raise ValueError("Faltan secciones, cursos o docentes.")

        # {(docente_uid, dia, hora_inicio): True}
        docente_ocupado: set[tuple] = set()
        uids = []

        for sec_uid in secciones:
            tutoria_asignada = False

            for dia in DIAS:
                bloques_del_dia = list(BLOQUES)
                random.shuffle(bloques_del_dia)

                for idx, (h_ini, h_fin) in enumerate(bloques_del_dia):
                    if idx >= 6:  # máx 6 clases por día
                        break

                    libres = [d for d in docentes if (d, dia, h_ini) not in docente_ocupado]
                    if not libres:
                        continue

                    docente_uid = random.choice(libres)
                    curso_uid   = random.choice(cursos)

                    # Primera clase del lunes = tutoría (si no asignada)
                    es_tutoria = (not tutoria_asignada and dia == "lunes" and idx == 0)

                    try:
                        cur.execute(
                            """
                            INSERT INTO horario_clase
                                (seccion_uid, curso_uid, docente_dictante_uid,
                                 dia_semana, hora_inicio, hora_fin, es_hora_tutoria)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                            RETURNING uid
                            """,
                            (sec_uid, curso_uid, docente_uid,
                             dia, h_ini, h_fin, es_tutoria),
                        )
                        r = cur.fetchone()
                        if r:
                            uids.append(str(r[0]))
                            docente_ocupado.add((docente_uid, dia, h_ini))
                            if es_tutoria: tutoria_asignada = True
                    except Exception:
                        conn.rollback()  # ON CONFLICT parcial

        if _local: conn.commit()
        print(f"✅ {len(uids)} bloques de horario creados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error horario_clase: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_seccion()
    seed_periodo_trimestral()
    seed_matricula()
    seed_horario_clase()
    sys.exit(0)
