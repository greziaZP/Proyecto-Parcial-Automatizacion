"""
seeds/relacion_padre_estudiante.py — Vínculo M:N padre ↔ estudiante (UUID pk propio).
"""
import sys
import random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool


def seed_relacion_padre_estudiante(conn=None) -> int:
    """
    Crea vínculos padre-estudiante.
    - Cada estudiante tiene 1 apoderado principal (su tutor_principal_uid).
    - 30% de estudiantes reciben un segundo apoderado extra (otro parentesco).
    Retorna cantidad de filas insertadas.
    """
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding relacion_padre_estudiante...")

        cur.execute("SELECT uid, tutor_principal_uid FROM estudiante WHERE tutor_principal_uid IS NOT NULL")
        estudiantes = [(str(r[0]), str(r[1])) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM padre_familia")
        todos_padres = [str(r[0]) for r in cur.fetchall()]

        PARENTESCOS_PPAL = ["padre", "madre"]
        PARENTESCOS_SEC  = ["madre", "padre", "abuelo", "tio", "hermano", "otro"]

        insertados = 0
        for est_uid, padre_uid in estudiantes:
            # Vínculo principal
            cur.execute(
                """
                INSERT INTO relacion_padre_estudiante
                    (padre_apoderado_uid, estudiante_uid, parentesco, es_apoderado_principal)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (padre_apoderado_uid, estudiante_uid) DO NOTHING
                """,
                (padre_uid, est_uid, random.choice(PARENTESCOS_PPAL)),
            )
            insertados += cur.rowcount

            # 30% con segundo apoderado
            if random.random() < 0.30:
                otros = [p for p in todos_padres if p != padre_uid]
                if otros:
                    cur.execute(
                        """
                        INSERT INTO relacion_padre_estudiante
                            (padre_apoderado_uid, estudiante_uid, parentesco, es_apoderado_principal)
                        VALUES (%s, %s, %s, FALSE)
                        ON CONFLICT (padre_apoderado_uid, estudiante_uid) DO NOTHING
                        """,
                        (random.choice(otros), est_uid, random.choice(PARENTESCOS_SEC)),
                    )
                    insertados += cur.rowcount

        if _local: conn.commit()
        print(f"✅ {insertados} vínculos padre-estudiante insertados")
        return insertados
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error relacion_padre_estudiante: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_relacion_padre_estudiante(); sys.exit(0)
