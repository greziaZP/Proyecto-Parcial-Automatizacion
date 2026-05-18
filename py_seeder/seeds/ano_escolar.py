"""
seeds/ano_escolar.py
====================
Inserta 2 años escolares:
  - 2024: histórico (activo=False)
  - 2025: año activo actual
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import get_connection, release_connection, close_pool


def seed_ano_escolar(conn=None) -> None:
    _local = conn is None
    if _local:
        conn = get_connection()

    cur = conn.cursor()
    try:
        print("🌱 Seeding ano_escolar...")

        anos = [
            ("2024", "2024-03-01", "2024-12-15", False),
            ("2025", "2025-03-01", "2025-12-15", True),
        ]

        for nombre, inicio, fin, activo in anos:
            cur.execute(
                """
                INSERT INTO ano_escolar (nombre, fecha_inicio, fecha_fin, activo)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (nombre) DO NOTHING
                """,
                (nombre, inicio, fin, activo),
            )

        if _local:
            conn.commit()
        print(f"✅ {len(anos)} años escolares insertados")

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding ano_escolar: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


if __name__ == "__main__":
    seed_ano_escolar()
