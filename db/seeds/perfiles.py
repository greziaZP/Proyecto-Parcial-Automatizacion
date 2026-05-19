"""
seeds/perfiles.py — Perfiles 1:1 con usuario (UUID shared PK).

PATRÓN v3: uid del perfil = uid del usuario (shared primary key).
  INSERT INTO docente (uid, nombres, apellidos, curso_especialidad_uid)
  VALUES (<usuario.uid>, ...)

Funciones:
  seed_docente()       → lee usuarios con rol='docente', inserta docente
  seed_auxiliar()      → lee usuarios con rol='auxiliar', inserta auxiliar
  seed_padre_familia() → lee usuarios con rol='padre', inserta padre_familia
  seed_estudiante()    → lee usuarios con rol='estudiante', inserta estudiante
                         (matricula_actual_uid se actualiza en estructura_academica.py)
"""
import sys
import random
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from faker import Faker
from config import get_connection, release_connection, close_pool

fake = Faker("es_ES")

CARGOS_AUXILIAR = [
    "Auxiliar Pabellón A", "Auxiliar Pabellón B",
    "Auxiliar de Patio",   "Auxiliar de Portería",
    "Auxiliar de Biblioteca",
]


def _dni_unico(usados: set[str]) -> str:
    while True:
        d = str(random.randint(10_000_000, 99_999_999))
        if d not in usados:
            usados.add(d); return d


# ─────────────────────────────────────────────────────────────────────────────
def seed_docente(conn=None) -> list[str]:
    """Inserta perfiles docente. Retorna lista de UIDs."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding docentes...")
        # Usuarios con rol='docente' sin perfil aún
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN docente d ON d.uid = u.uid
            WHERE u.rol = 'docente' AND d.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        # UIDs de cursos disponibles para especialidad
        cur.execute("SELECT uid FROM curso")
        cursos = [str(r[0]) for r in cur.fetchall()]
        if not cursos:
            raise ValueError("No hay cursos. Ejecuta seed_curso() primero.")

        uids = []
        for uid in usuarios:
            cur.execute(
                """
                INSERT INTO docente (uid, nombres, apellidos, curso_especialidad_uid)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO NOTHING
                """,
                (uid, fake.first_name(), fake.last_name(), random.choice(cursos)),
            )
            if cur.rowcount: uids.append(uid)

        if _local: conn.commit()
        print(f"✅ {len(uids)} docentes insertados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error docente: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_auxiliar(conn=None) -> list[str]:
    """Inserta perfiles auxiliar. Retorna lista de UIDs."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding auxiliares...")
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN auxiliar a ON a.uid = u.uid
            WHERE u.rol = 'auxiliar' AND a.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        uids = []
        for i, uid in enumerate(usuarios):
            cargo = CARGOS_AUXILIAR[i % len(CARGOS_AUXILIAR)]
            cur.execute(
                """
                INSERT INTO auxiliar (uid, nombres, apellidos, cargo_asignado)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (uid) DO NOTHING
                """,
                (uid, fake.first_name(), fake.last_name(), cargo),
            )
            if cur.rowcount: uids.append(uid)

        if _local: conn.commit()
        print(f"✅ {len(uids)} auxiliares insertados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error auxiliar: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_padre_familia(conn=None) -> list[str]:
    """Inserta perfiles padre_familia. Retorna lista de UIDs."""
    _local = conn is None
    if _local: conn = get_connection()
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
        uids = []
        for uid in usuarios:
            cur.execute(
                """
                INSERT INTO padre_familia
                    (uid, nombres, apellidos, dni_apoderado, telefono_contacto)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO NOTHING
                """,
                (uid, fake.first_name(), fake.last_name(),
                 _dni_unico(dnis), fake.phone_number()[:30]),
            )
            if cur.rowcount: uids.append(uid)

        if _local: conn.commit()
        print(f"✅ {len(uids)} padres insertados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error padre_familia: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_estudiante(conn=None) -> list[str]:
    """
    Inserta perfiles estudiante con tutor_principal_uid asignado.
    matricula_actual_uid se deja NULL — se actualiza en seed_matricula().
    Retorna lista de UIDs.
    """
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding estudiantes...")
        cur.execute("""
            SELECT u.uid FROM usuario u
            LEFT JOIN estudiante e ON e.uid = u.uid
            WHERE u.rol = 'estudiante' AND e.uid IS NULL
        """)
        usuarios = [str(r[0]) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM padre_familia ORDER BY uid")
        padres = [str(r[0]) for r in cur.fetchall()]
        if not padres:
            raise ValueError("No hay padres. Ejecuta seed_padre_familia() primero.")

        dnis: set[str] = set()
        hoy = date.today()
        uids = []

        for i, uid in enumerate(usuarios):
            tutor_uid = padres[i % len(padres)]
            edad = random.randint(11, 17)
            # Fecha nacimiento: año - edad, mes y día aleatorios válidos
            fec_nac = date(hoy.year - edad, random.randint(1, 12), random.randint(1, 28))

            cur.execute(
                """
                INSERT INTO estudiante
                    (uid, nombres, apellidos, dni_estudiante,
                     fecha_nacimiento, tutor_principal_uid)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (uid) DO NOTHING
                """,
                (uid, fake.first_name(), fake.last_name(),
                 _dni_unico(dnis), fec_nac, tutor_uid),
            )
            if cur.rowcount: uids.append(uid)

        if _local: conn.commit()
        print(f"✅ {len(uids)} estudiantes insertados  (matricula_actual_uid=NULL por ahora)")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error estudiante: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_docente()
    seed_auxiliar()
    seed_padre_familia()
    seed_estudiante()
    sys.exit(0)
