"""
seeds/permiso_salida.py — Permisos de retiro anticipado (UUID PK).

Genera ~2 permisos por sección del año activo.
  - matricula_uid          → matrícula activa del estudiante
  - padre_solicitante_uid  → tutor_principal_uid del estudiante
  - auxiliar_registrador_uid → auxiliar obligatorio
  - auxiliar_autorizador_uid → auxiliar opcional (80% de los casos)
  - hora_salida            → TIME (no timestamp)
"""
import sys
import random
from datetime import date, time, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool, SeedConfig


def seed_permiso_salida(conn=None) -> list[str]:
    """Retorna lista de UIDs de permisos creados."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding permisos de salida...")

        # Matrículas activas con su tutor principal
        cur.execute("""
            SELECT m.uid, e.tutor_principal_uid
            FROM matricula m
            JOIN estudiante e ON e.uid = m.estudiante_uid
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE
              AND m.estado_matricula = 'activa'
              AND e.tutor_principal_uid IS NOT NULL
        """)
        matriculas = [(str(r[0]), str(r[1])) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM auxiliar")
        auxiliares = [str(r[0]) for r in cur.fetchall()]
        if not auxiliares:
            raise ValueError("No hay auxiliares. Ejecuta seed_auxiliar() primero.")

        MOTIVOS = [
            "Control médico de rutina",
            "Cita odontológica programada",
            "Trámite familiar urgente",
            "Consulta médica especialista",
            "Emergencia familiar",
        ]

        # Tomar ~30% de matrículas para generar permisos
        muestra = random.sample(matriculas, max(1, len(matriculas) // 3))
        inicio_rango = date(2025, 3, 10)

        uids = []
        for mat_uid, padre_uid in muestra:
            fecha = inicio_rango + timedelta(days=random.randint(0, SeedConfig.DIAS_HISTORIAL))
            # Hora de salida entre 10:00 y 14:00
            hora_sal = time(random.randint(10, 13), random.choice([0, 15, 30, 45]))
            aux_reg = random.choice(auxiliares)
            aux_aut = random.choice(auxiliares) if random.random() < 0.80 else None

            cur.execute(
                """
                INSERT INTO permiso_salida
                    (matricula_uid, padre_solicitante_uid,
                     auxiliar_autorizador_uid, auxiliar_registrador_uid,
                     fecha_permiso, hora_salida, motivo_salida)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING uid
                """,
                (mat_uid, padre_uid, aux_aut, aux_reg,
                 fecha, hora_sal, random.choice(MOTIVOS)),
            )
            r = cur.fetchone()
            if r: uids.append(str(r[0]))

        if _local: conn.commit()
        print(f"✅ {len(uids)} permisos de salida insertados")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error permiso_salida: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_permiso_salida(); sys.exit(0)
