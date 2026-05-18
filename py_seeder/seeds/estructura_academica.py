"""
seeds/estructura_academica.py
==============================
Crea:
  1. seccion      — 10 secciones (2 por grado, niveles 1°-5° de secundaria)
  2. periodo_trimestral — 3 períodos por año escolar activo
  3. matricula    — todos los estudiantes en una sección
  4. horario_clase — ~6 bloques por día × 5 días × sección

IMPORTANTE sobre seccion.tutor_uid:
  El campo es nullable, se asigna un docente como tutor de sección.
  Un docente puede ser tutor de solo una sección (el índice parcial
  uq_tutoria_seccion en horario_clase lo garantiza, pero aquí sólo
  asignamos el campo informativo de seccion.tutor_uid).
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import random
from datetime import date, timedelta
from config import get_connection, release_connection, close_pool, SeedConfig

# Estructura de secciones: grado → nivel
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

# Bloques de clases (hora_inicio, hora_fin)
BLOQUES_HORARIO = [
    ("07:30", "08:15"),
    ("08:15", "09:00"),
    ("09:00", "09:45"),
    ("10:00", "10:45"),  # recreo de 09:45-10:00
    ("10:45", "11:30"),
    ("11:30", "12:15"),
    ("14:00", "14:45"),  # tarde
    ("14:45", "15:30"),
]

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes"]


# ─────────────────────────────────────────────────────────────────────────────
def seed_seccion(conn=None) -> list[str]:
    """Inserta secciones para el año activo. Retorna lista de UIDs."""
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding secciones...")

        # Año activo
        cur.execute("SELECT uid FROM ano_escolar WHERE activo = TRUE LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise ValueError("No hay año escolar activo.")
        ano_uid = str(row[0])

        # Docentes disponibles para asignar como tutores
        cur.execute("SELECT uid FROM docente")
        docentes = [str(r[0]) for r in cur.fetchall()]

        uids_sec = []
        for grado, nivel, codigo in SECCIONES_DEF:
            tutor = random.choice(docentes) if docentes else None
            cur.execute(
                """
                INSERT INTO seccion
                    (ano_escolar_uid, grado_academico, nivel_educativo,
                     codigo_seccion, tutor_uid)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (ano_escolar_uid, grado_academico, codigo_seccion)
                DO NOTHING
                RETURNING uid
                """,
                (ano_uid, grado, nivel, codigo, tutor),
            )
            row = cur.fetchone()
            if row:
                uids_sec.append(str(row[0]))

        if _local:
            conn.commit()
        print(f"✅ {len(uids_sec)} secciones insertadas")
        return uids_sec

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding seccion: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_periodo_trimestral(conn=None) -> list[str]:
    """Inserta 3 períodos trimestrales para el año activo."""
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding períodos trimestrales...")

        cur.execute(
            "SELECT uid, fecha_inicio FROM ano_escolar WHERE activo = TRUE LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("No hay año escolar activo.")
        ano_uid, fecha_inicio = str(row[0]), row[1]

        # 3 trimestres de ~13 semanas c/u
        periodos = []
        inicio = fecha_inicio
        for n in range(1, 4):
            fin = inicio + timedelta(weeks=13)
            periodos.append((ano_uid, n, inicio, fin))
            inicio = fin + timedelta(days=1)

        uids = []
        for ano_uid, num, fi, ff in periodos:
            cur.execute(
                """
                INSERT INTO periodo_trimestral
                    (ano_escolar_uid, numero_trimestre, fecha_inicio, fecha_fin)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ano_escolar_uid, numero_trimestre) DO NOTHING
                RETURNING uid
                """,
                (ano_uid, num, fi, ff),
            )
            row = cur.fetchone()
            if row:
                uids.append(str(row[0]))

        if _local:
            conn.commit()
        print(f"✅ {len(uids)} períodos trimestrales insertados")
        return uids

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding periodo_trimestral: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_matricula(conn=None) -> list[str]:
    """
    Matricula TODOS los estudiantes en una sección del año activo.
    Distribución: round-robin entre secciones disponibles.
    Retorna lista de UIDs de matrícula.
    """
    _local = conn is None
    if _local:
        conn = get_connection()
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
        if not secciones:
            raise ValueError("No hay secciones para el año activo.")

        # Estudiantes sin matrícula en año activo
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
                (est_uid, sec_uid, date(2025, 3, 1)),
            )
            row = cur.fetchone()
            if row:
                uids.append(str(row[0]))

        if _local:
            conn.commit()
        print(f"✅ {len(uids)} matrículas insertadas")
        return uids

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding matricula: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_horario_clase(conn=None) -> list[str]:
    """
    Genera horario semanal para cada sección.
    Asigna cursos y docentes sin conflictos (un docente no puede estar
    en dos lugares al mismo tiempo).

    Retorna lista de UIDs de horario creados.
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding horarios de clase...")

        cur.execute("""
            SELECT s.uid FROM seccion s
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE
        """)
        secciones = [str(r[0]) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM curso")
        cursos = [str(r[0]) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM docente")
        docentes = [str(r[0]) for r in cur.fetchall()]

        # Rastrear disponibilidad docente: {(docente_uid, dia, hora): True}
        docente_ocupado: set[tuple] = set()
        uids = []

        for sec_uid in secciones:
            tutor_asignado = False
            for dia in DIAS:
                bloques_disponibles = list(BLOQUES_HORARIO)
                random.shuffle(bloques_disponibles)

                for bloque_idx, (hora_inicio, hora_fin) in enumerate(bloques_disponibles):
                    if bloque_idx >= 6:  # máx 6 clases por día por sección
                        break

                    # Encontrar docente libre en este slot
                    docentes_libres = [
                        d for d in docentes
                        if (d, dia, hora_inicio) not in docente_ocupado
                    ]
                    if not docentes_libres:
                        continue

                    docente_uid = random.choice(docentes_libres)
                    curso_uid = random.choice(cursos)

                    # Primera clase del lunes es tutoría (si no se ha asignado)
                    es_tutoria = (
                        not tutor_asignado
                        and dia == "lunes"
                        and bloque_idx == 0
                    )

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
                             dia, hora_inicio, hora_fin, es_tutoria),
                        )
                        row = cur.fetchone()
                        if row:
                            uids.append(str(row[0]))
                            docente_ocupado.add((docente_uid, dia, hora_inicio))
                            if es_tutoria:
                                tutor_asignado = True
                    except Exception:
                        # El índice uq_tutoria_seccion puede rechazar duplicados
                        conn.rollback()  # rollback savepoint
                        continue

        if _local:
            conn.commit()
        print(f"✅ {len(uids)} bloques de horario insertados")
        return uids

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding horario_clase: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


if __name__ == "__main__":
    seed_seccion()
    seed_periodo_trimestral()
    seed_matricula()
    seed_horario_clase()
