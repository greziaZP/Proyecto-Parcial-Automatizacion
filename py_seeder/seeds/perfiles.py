"""
seeds/perfiles.py
=================
Crea los 4 perfiles 1:1 con usuario usando SHARED PRIMARY KEY (UUID):
  - docente      → uid = usuario.uid donde rol='docente'
  - auxiliar     → uid = usuario.uid donde rol='auxiliar'
  - padre_familia → uid = usuario.uid donde rol='padre'
  - estudiante   → uid = usuario.uid donde rol='estudiante'

PATRÓN: Consulta la tabla usuario filtrando por rol → inserta perfil
con el mismo uid. No asume rangos de IDs.

El seeder de estudiante también asigna tutor_principal_uid al padre
correspondiente (en proporción 4 estudiantes por padre aprox.).
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import random
from faker import Faker
from config import get_connection, release_connection, close_pool

fake = Faker("es_PE")

# Cargos típicos para auxiliares de colegio peruano
CARGOS_AUXILIAR = [
    "Auxiliar de Pabellón A",
    "Auxiliar de Pabellón B",
    "Auxiliar de Patio",
    "Auxiliar de Portería",
    "Auxiliar de Biblioteca",
]


def _dni_unico(usados: set[str]) -> str:
    while True:
        dni = str(random.randint(10_000_000, 99_999_999))
        if dni not in usados:
            usados.add(dni)
            return dni


# ─────────────────────────────────────────────────────────────────────────────
def seed_docente(conn=None) -> list[str]:
    """Retorna lista de UIDs de docentes insertados."""
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding docentes...")
        # Obtener usuarios con rol='docente' sin perfil aún
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN docente d ON d.uid = u.uid
            WHERE u.rol = 'docente' AND d.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        # Obtener cursos disponibles para asignar especialidad
        cur.execute("SELECT uid FROM curso")
        cursos = [str(r[0]) for r in cur.fetchall()]
        if not cursos:
            raise ValueError("No hay cursos en BD. Ejecuta seed_curso primero.")

        uids_insertados = []
        for uid in usuarios:
            cur.execute(
                """
                INSERT INTO docente (uid, nombres, apellidos, curso_especialidad_uid)
                VALUES (%s, %s, %s, %s)
                """,
                (uid, fake.first_name(), fake.last_name(),
                 random.choice(cursos)),
            )
            uids_insertados.append(uid)

        if _local:
            conn.commit()
        print(f"✅ {len(uids_insertados)} docentes insertados")
        return uids_insertados

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding docente: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_auxiliar(conn=None) -> list[str]:
    """Retorna lista de UIDs de auxiliares insertados."""
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding auxiliares...")
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN auxiliar a ON a.uid = u.uid
            WHERE u.rol = 'auxiliar' AND a.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        uids_insertados = []
        for i, uid in enumerate(usuarios):
            cargo = CARGOS_AUXILIAR[i % len(CARGOS_AUXILIAR)]
            cur.execute(
                """
                INSERT INTO auxiliar (uid, nombres, apellidos, cargo_asignado)
                VALUES (%s, %s, %s, %s)
                """,
                (uid, fake.first_name(), fake.last_name(), cargo),
            )
            uids_insertados.append(uid)

        if _local:
            conn.commit()
        print(f"✅ {len(uids_insertados)} auxiliares insertados")
        return uids_insertados

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding auxiliar: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_padre_familia(conn=None) -> list[str]:
    """Retorna lista de UIDs de padres insertados."""
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding padres de familia...")
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN padre_familia pf ON pf.uid = u.uid
            WHERE u.rol = 'padre' AND pf.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        dnis: set[str] = set()
        uids_insertados = []
        for uid in usuarios:
            cur.execute(
                """
                INSERT INTO padre_familia
                    (uid, nombres, apellidos, dni_apoderado, telefono_contacto)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (uid, fake.first_name(), fake.last_name(),
                 _dni_unico(dnis), fake.phone_number()[:30]),
            )
            uids_insertados.append(uid)

        if _local:
            conn.commit()
        print(f"✅ {len(uids_insertados)} padres insertados")
        return uids_insertados

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding padre_familia: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_estudiante(conn=None) -> list[str]:
    """
    Crea perfiles de estudiante y asigna tutor_principal_uid.
    Relación: ~4 estudiantes por padre (round-robin).
    Retorna lista de UIDs de estudiantes insertados.
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding estudiantes...")
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN estudiante e ON e.uid = u.uid
            WHERE u.rol = 'estudiante' AND e.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        # Obtener padres disponibles
        cur.execute("SELECT uid FROM padre_familia ORDER BY uid")
        padres = [str(r[0]) for r in cur.fetchall()]
        if not padres:
            raise ValueError("No hay padres en BD. Ejecuta seed_padre_familia primero.")

        dnis: set[str] = set()
        uids_insertados = []
        for i, uid in enumerate(usuarios):
            tutor_uid = padres[i % len(padres)]
            # Edad secundaria peruana: 11-17 años
            from datetime import date
            hoy = date.today()
            edad = random.randint(11, 17)
            fecha_nac = date(hoy.year - edad,
                             random.randint(1, 12),
                             random.randint(1, 28))

            cur.execute(
                """
                INSERT INTO estudiante
                    (uid, nombres, apellidos, dni_estudiante,
                     fecha_nacimiento, tutor_principal_uid)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (uid, fake.first_name(), fake.last_name(),
                 _dni_unico(dnis), fecha_nac, tutor_uid),
            )
            uids_insertados.append(uid)

        if _local:
            conn.commit()
        print(f"✅ {len(uids_insertados)} estudiantes insertados")
        return uids_insertados

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding estudiante: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    seed_docente()
    seed_auxiliar()
    seed_padre_familia()
    seed_estudiante()
