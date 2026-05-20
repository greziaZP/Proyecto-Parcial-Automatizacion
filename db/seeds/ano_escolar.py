"""seeds/ano_escolar.py — Inserta años escolares (UUID PK)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool


def seed_ano_escolar(conn=None) -> dict[str, str]:
    """
    Inserta 2 años escolares y retorna {nombre: uid}.
    - 2024: histórico (activo=False)
    - 2025: activo
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    anos = [
        ("2024", "2024-03-04", "2024-12-13", False),
        ("2025", "2025-03-03", "2025-12-12", True),
    ]
    
    uids: dict[str, str] = {}

    try:
        print("🌱 Seeding ano_escolar...")
        for nombre, inicio, fin, activo in anos:
            cur.execute(
                """
                INSERT INTO ano_escolar (nombre, fecha_inicio, fecha_fin, activo)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (nombre) DO UPDATE SET activo = EXCLUDED.activo
                RETURNING uid, nombre
                """,
                (nombre, inicio, fin, activo),
            )
            uid, nom = cur.fetchone()
            uids[nom] = str(uid)

        if _local:
            conn.commit()
        print(f"✅ {len(uids)} años escolares insertados → {list(uids.keys())}")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error ano_escolar: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_ano_escolar(); sys.exit(0)
