"""
seeds/usuario.py
================
NUEVO ESQUEMA (UUID + shared PK):
  - usuario ya NO tiene nombres/apellidos (eso vive en el perfil).
  - Sólo: uid, email, rol, password_hash, activo, creado_en.

Distribución de roles:
  - 2  admin  (hardcodeados — el equipo)
  - N  docente (SeedConfig.NUM_DOCENTES)
  - M  auxiliar (SeedConfig.NUM_AUXILIARES)
  - P  estudiante (SeedConfig.NUM_ESTUDIANTES)
  - Q  padre (SeedConfig.NUM_PADRES)

Retorna los UIDs agrupados por rol para que los seeders de perfil
los usen sin hacer otra query.
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from faker import Faker
from config import get_connection, release_connection, close_pool, SeedConfig

fake = Faker("es_PE")  # Locale peruano


def seed_usuario(conn=None) -> dict[str, list[str]]:
    """
    Inserta usuarios y retorna dict con UIDs por rol:
      { 'admin': [...], 'docente': [...], 'auxiliar': [...],
        'estudiante': [...], 'padre': [...] }
    """
    _local = conn is None
    if _local:
        conn = get_connection()

    cur = conn.cursor()
    uids_por_rol: dict[str, list[str]] = {
        "admin": [], "docente": [], "auxiliar": [],
        "estudiante": [], "padre": [],
    }

    try:
        print("🌱 Seeding usuarios...")
        emails_usados: set[str] = set()

        def _unique_email(base: str | None = None) -> str:
            while True:
                email = base or fake.unique.email()
                if email not in emails_usados:
                    emails_usados.add(email)
                    return email

        def _insert_usuario(email: str, rol: str) -> str:
            cur.execute(
                """
                INSERT INTO usuario (email, rol, password_hash)
                VALUES (%s, %s, %s)
                RETURNING uid
                """,
                (email, rol, SeedConfig.DEFAULT_HASH),
            )
            uid = str(cur.fetchone()[0])
            uids_por_rol[rol].append(uid)
            return uid

        # ── 2 ADMINS (hardcodeados) ──────────────────────────────────────────
        for admin in SeedConfig.ADMIN_USUARIOS:
            _insert_usuario(admin["email"], admin["rol"])

        # ── DOCENTES ─────────────────────────────────────────────────────────
        for _ in range(SeedConfig.NUM_DOCENTES):
            _insert_usuario(_unique_email(), "docente")

        # ── AUXILIARES ───────────────────────────────────────────────────────
        for _ in range(SeedConfig.NUM_AUXILIARES):
            _insert_usuario(_unique_email(), "auxiliar")

        # ── ESTUDIANTES ──────────────────────────────────────────────────────
        for _ in range(SeedConfig.NUM_ESTUDIANTES):
            _insert_usuario(_unique_email(), "estudiante")

        # ── PADRES ───────────────────────────────────────────────────────────
        for _ in range(SeedConfig.NUM_PADRES):
            _insert_usuario(_unique_email(), "padre")

        if _local:
            conn.commit()

        total = sum(len(v) for v in uids_por_rol.values())
        print(f"✅ {total} usuarios insertados")
        print(f"   • {len(uids_por_rol['admin'])} admins")
        print(f"   • {len(uids_por_rol['docente'])} docentes")
        print(f"   • {len(uids_por_rol['auxiliar'])} auxiliares")
        print(f"   • {len(uids_por_rol['estudiante'])} estudiantes")
        print(f"   • {len(uids_por_rol['padre'])} padres")
        return uids_por_rol

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding usuario: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


if __name__ == "__main__":
    seed_usuario()
