"""
seeds/fuga.py — Registros de evasión de clase (UUID PK).

Toma asistencias con estado='falta' sin justificacion y crea fugas (~20%).
  - auxiliar_detector_uid    → quién detectó (obligatorio)
  - auxiliar_registrador_uid → quién registró (obligatorio)
  - auxiliar_resolutor_uid   → quién cerró (nullable, 60% de resueltas)
  - justificacion_uid        → si el padre justificó después (nullable)
"""
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool



def seed_fuga(conn=None) -> int:
    """Retorna cantidad de fugas insertadas."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding fugas...")

        # Asistencias con falta sin justificacion (candidatas a fuga)
        cur.execute("""
            SELECT uid FROM asistencia_clase
            WHERE estado_asistencia = 'falta'
              AND justificacion_uid IS NULL
            ORDER BY RANDOM()
        """)
        candidatos = [str(r[0]) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM auxiliar")
        auxiliares = [str(r[0]) for r in cur.fetchall()]
        if not auxiliares:
            raise ValueError("No hay auxiliares.")

        # Tomar 20% de candidatos como fugas
        muestra = random.sample(candidatos, max(1, int(len(candidatos) * 0.20)))

        ESTADOS_F = ["detectada", "notificada", "resuelta"]
        PESOS_F   = [0.3, 0.3, 0.4]

        OBSERVACIONES = [
            "Alumno salió sin autorización por puerta trasera.",
            "Alumno no regresó del recreo.",
            "Se detectó ausencia en el pasillo durante clase.",
            "Portería reportó salida no autorizada.",
            "Alumno no se presentó a clase después del recreo.",
        ]

        base_dt = datetime(2025, 3, 10, 10, 0, 0)
        insertados = 0

        for ac_uid in muestra:
            det   = random.choice(auxiliares)
            reg   = random.choice(auxiliares)
            estado = random.choices(ESTADOS_F, weights=PESOS_F)[0]
            deteccion = base_dt + timedelta(
                days=random.randint(0, 60),
                hours=random.randint(0, 5),
                minutes=random.randint(0, 59),
            )
            resolutor = None
            resolucion = None
            if estado == "resuelta":
                resolutor  = random.choice(auxiliares)
                resolucion = deteccion + timedelta(hours=random.randint(1, 4))

            cur.execute(
                """
                INSERT INTO fuga (
                    asistencia_clase_uid, auxiliar_detector_uid,
                    auxiliar_registrador_uid, fecha_hora_deteccion,
                    estado_fuga, auxiliar_resolutor_uid, fecha_hora_resolucion,
                    observacion_caso
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
                """,
                (ac_uid, det, reg, deteccion, estado,
                 resolutor, resolucion, random.choice(OBSERVACIONES)),
            )
            insertados += cur.rowcount

        if _local: conn.commit()
        print(f"✅ {insertados} fugas insertadas")
        return insertados
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error fuga: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_fuga(); sys.exit(0)
