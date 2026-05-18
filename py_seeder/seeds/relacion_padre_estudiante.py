"""
seeds/relacion_padre_estudiante.py
===================================
Crea el vínculo M:N padre ↔ estudiante con parentesco y apoderado principal.

Lógica:
  - El tutor_principal_uid de cada estudiante es su apoderado principal.
  - Adicionalmente, un 30% de estudiantes tiene un segundo apoderado (madre/padre).
  - Se evitan duplicados con ON CONFLICT DO NOTHING.
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import random
from config import get_connection, release_connection, close_pool

PARENTESCOS = ["padre", "madre", "abuelo", "tio", "hermano", "otro"]


def seed_relacion_padre_estudiante(conn=None) -> None:
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding relaciones padre-estudiante...")

        # Obtener todos los estudiantes con su tutor principal
        cur.execute("""
            SELECT uid, tutor_principal_uid FROM estudiante
            WHERE tutor_principal_uid IS NOT NULL
        """)
        estudiantes = cur.fetchall()  # [(est_uid, padre_uid), ...]

        # Obtener todos los padres disponibles
        cur.execute("SELECT uid FROM padre_familia")
        padres = [str(r[0]) for r in cur.fetchall()]

        insertados = 0

        for est_uid, padre_uid in estudiantes:
            est_uid = str(est_uid)
            padre_uid = str(padre_uid)

            # Vínculo principal (padre/madre según azar)
            parentesco_ppal = random.choice(["padre", "madre"])
            cur.execute(
                """
                INSERT INTO relacion_padre_estudiante
                    (padre_apoderado_uid, estudiante_uid, parentesco, es_apoderado_principal)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (padre_apoderado_uid, estudiante_uid) DO NOTHING
                """,
                (padre_uid, est_uid, parentesco_ppal),
            )
            insertados += cur.rowcount

            # 30% de estudiantes tiene un segundo apoderado distinto
            if random.random() < 0.30 and len(padres) > 1:
                segundo = random.choice([p for p in padres if p != padre_uid])
                parentesco_seg = random.choice(
                    ["madre", "padre", "abuelo", "tio", "hermano", "otro"]
                )
                cur.execute(
                    """
                    INSERT INTO relacion_padre_estudiante
                        (padre_apoderado_uid, estudiante_uid, parentesco, es_apoderado_principal)
                    VALUES (%s, %s, %s, FALSE)
                    ON CONFLICT (padre_apoderado_uid, estudiante_uid) DO NOTHING
                    """,
                    (segundo, est_uid, parentesco_seg),
                )
                insertados += cur.rowcount

        if _local:
            conn.commit()
        print(f"✅ {insertados} vínculos padre-estudiante insertados")

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding relacion_padre_estudiante: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


if __name__ == "__main__":
    seed_relacion_padre_estudiante()
