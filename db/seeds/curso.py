"""seeds/curso.py — Inserta cursos de secundaria peruana (UUID PK)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool

CURSOS = [
    ("Comunicación",                        "COM"),
    ("Matemática",                          "MAT"),
    ("Historia, Geografía y Economía",      "HGE"),
    ("Formación Ciudadana y Cívica",        "FCC"),
    ("Persona, Familia y RR.HH.",           "PFR"),
    ("Educación para el Trabajo",           "EPT"),
    ("Ciencia, Tecnología y Ambiente",      "CTA"),
    ("Inglés",                              "ING"),
    ("Educación Física",                    "EDF"),
    ("Arte y Cultura",                      "ART"),
    ("Religión",                            "REL"),
    ("Tutoría",                             "TUT"),
]


def seed_curso(conn=None, cursos: list[tuple] | None = None) -> dict[str, str]:
    """
    Inserta cursos y retorna {codigo: uid}.
    Args:
        cursos: lista de (nombre, codigo). Si None usa CURSOS por defecto.
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()
    lista = cursos or CURSOS
    uids: dict[str, str] = {}

    try:
        print("🌱 Seeding cursos...")
        for nombre, codigo in lista:
            cur.execute(
                """
                INSERT INTO curso (nombre, codigo)
                VALUES (%s, %s)
                ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING uid, codigo
                """,
                (nombre, codigo),
            )
            uid, cod = cur.fetchone()
            uids[cod] = str(uid)

        if _local:
            conn.commit()
        print(f"✅ {len(uids)} cursos insertados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error curso: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_curso(); sys.exit(0)
