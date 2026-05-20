"""
seeds/usuario.py — Inserta usuarios (UUID PK central de auth).

Nueva tabla usuario (v3):
  uid, email, rol, password_hash, activo, creado_en
  → NO tiene nombres/apellidos (eso vive en el perfil 1:1)

Distribución configurable vía SeedConfig:
  2 admins hardcodeados + N docentes + M auxiliares + P estudiantes + Q padres
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from faker import Faker
from config import get_connection, release_connection, close_pool, SeedConfig

fake = Faker("es_ES")



def seed_usuario(conn=None) -> dict[str, list[str]]:
    """
    Inserta usuarios y retorna UIDs agrupados por rol:
    { 'admin': [...], 'docente': [...], 'auxiliar': [...],
      'estudiante': [...], 'padre': [...] }
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    uids: dict[str, list[str]] = {
        "admin": [], "docente": [], "auxiliar": [],
        "estudiante": [], "padre": [],
    }
    emails_usados: set[str] = set()

    def _email_unico(base: str | None = None) -> str:
        while True:
            e = base or f"{fake.user_name()}{fake.random_int(1,9999)}@upao.edu.pe"
            if e not in emails_usados:
                emails_usados.add(e)
                return e

    def _insertar(email: str, rol: str) -> str:
        cur.execute(
            """
            INSERT INTO usuario (email, rol, password_hash)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET rol = EXCLUDED.rol
            RETURNING uid
            """,
            (email, rol, SeedConfig.DEFAULT_HASH),
        )
        uid = str(cur.fetchone()[0])
        uids[rol].append(uid)
        return uid

    try:
        print("🌱 Seeding usuarios...")

        # 2 admins reales del equipo
        for a in SeedConfig.ADMIN_USUARIOS:
            _insertar(a["email"], a["rol"])

        # Faker usuarios por rol
        for _ in range(SeedConfig.NUM_DOCENTES):
            _insertar(_email_unico(), "docente")
        for _ in range(SeedConfig.NUM_AUXILIARES):
            _insertar(_email_unico(), "auxiliar")
        for _ in range(SeedConfig.NUM_ESTUDIANTES):
            _insertar(_email_unico(), "estudiante")
        for _ in range(SeedConfig.NUM_PADRES):
            _insertar(_email_unico(), "padre")

        if _local:
            conn.commit()

        total = sum(len(v) for v in uids.values())
        print(f"✅ {total} usuarios insertados")
        print(f"   • {len(uids['admin'])} admins  • {len(uids['docente'])} docentes"
              f"  • {len(uids['auxiliar'])} auxiliares")
        print(f"   • {len(uids['estudiante'])} estudiantes  • {len(uids['padre'])} padres")
        return uids

    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error usuario: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_usuario(); sys.exit(0)
