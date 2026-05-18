"""
seeds/curso.py
==============
Inserta los cursos del colegio secundario peruano.
Parametrizable: puede recibir una lista externa o usar los hardcodeados.
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import get_connection, release_connection, close_pool, SeedConfig

# Cursos típicos de secundaria peruana
CURSOS_DEFAULT = [
    ("Comunicación",                   "COM"),
    ("Matemática",                     "MAT"),
    ("Historia, Geografía y Economía", "HGE"),
    ("Formación Ciudadana y Cívica",   "FCC"),
    ("Persona, Familia y RR.HH.",      "PFR"),
    ("Educación para el Trabajo",      "EPT"),
    ("Ciencia, Tecnología y Ambiente", "CTA"),
    ("Inglés",                         "ING"),
    ("Educación Física",               "EDF"),
    ("Arte y Cultura",                 "ART"),
    ("Religión",                       "REL"),
    ("Tutoría",                        "TUT"),
]


def seed_curso(conn=None, cursos: list[tuple] | None = None) -> None:
    """
    Args:
        conn:   Conexión existente (si None, crea una nueva).
        cursos: Lista de (nombre, codigo). Si None usa CURSOS_DEFAULT.
    """
    _local = conn is None
    if _local:
        conn = get_connection()

    cur = conn.cursor()
    cursos = cursos or CURSOS_DEFAULT

    try:
        print("🌱 Seeding cursos...")
        insertados = 0

        for nombre, codigo in cursos:
            cur.execute(
                """
                INSERT INTO curso (nombre, codigo)
                VALUES (%s, %s)
                ON CONFLICT (codigo) DO NOTHING
                """,
                (nombre, codigo),
            )
            insertados += cur.rowcount

        if _local:
            conn.commit()
        print(f"✅ {insertados} cursos insertados")

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding curso: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


if __name__ == "__main__":
    seed_curso()
