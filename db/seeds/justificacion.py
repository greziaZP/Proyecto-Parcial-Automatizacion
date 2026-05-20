"""
seeds/justificacion.py
========================
Crea justificaciones vinculadas a registros de asistencia_clase existentes.

LÓGICA v3:
  - justificacion.asistencia_clase_uid es NOT NULL → debe apuntar a un
    registro real de asistencia_clase.
  - Toma los registros con estado IN ('falta','tardanza','justificada') y
    crea justificaciones para un subconjunto (~40%).
  - Después de insertar, actualiza asistencia_clase.justificacion_uid
    y registro_ingreso.justificacion_uid donde corresponda.
"""
import sys
import random
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool


TIPOS       = ["medica", "familiar", "viaje", "otra"]
ESTADOS_J   = ["pendiente", "aprobada", "rechazada"]
PESOS_EST   = [0.3, 0.6, 0.1]          # pendiente 30%, aprobada 60%, rechazada 10%
DESCRIPCIONES = [
    "El alumno presentó malestar general con fiebre alta.",
    "Viaje familiar por emergencia de salud de familiar directo.",
    "Cita médica con especialista pediatra programada con anterioridad.",
    "Trámite administrativo familiar de carácter urgente.",
    "Participación en actividad deportiva interescolar autorizada.",
    "Control médico preventivo con certificado adjunto.",
]


def seed_justificacion(conn=None) -> list[str]:
    """
    Inserta justificaciones y actualiza FKs en asistencia_clase y registro_ingreso.
    Retorna lista de UIDs de justificaciones creadas.
    """
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding justificaciones...")

        # Candidatos: asistencias con falta, tardanza o justificada
        cur.execute("""
            SELECT ac.uid, m.estudiante_uid
            FROM asistencia_clase ac
            JOIN matricula m ON m.uid = ac.matricula_uid
            WHERE ac.estado_asistencia IN ('falta','tardanza','justificada')
              AND ac.justificacion_uid IS NULL
            ORDER BY RANDOM()
        """)
        candidatos = [(str(r[0]), str(r[1])) for r in cur.fetchall()]

        # Tomar 40% de candidatos
        muestra = random.sample(candidatos, max(1, int(len(candidatos) * 0.40)))

        # Padres y docentes disponibles
        cur.execute("SELECT uid FROM padre_familia")
        padres = [str(r[0]) for r in cur.fetchall()]
        cur.execute("SELECT uid FROM docente")
        docentes = [str(r[0]) for r in cur.fetchall()]

        uids = []
        for ac_uid, est_uid in muestra:
            # Buscar el padre del estudiante
            cur.execute(
                "SELECT tutor_principal_uid FROM estudiante WHERE uid = %s", (est_uid,)
            )
            r = cur.fetchone()
            padre_uid = str(r[0]) if r and r[0] else random.choice(padres)

            estado   = random.choices(ESTADOS_J, weights=PESOS_EST)[0]
            tipo     = random.choice(TIPOS)
            f_pres   = date(2025, 3, 10) + timedelta(days=random.randint(0, 60))
            f_inicio = f_pres + timedelta(days=random.randint(0, 2))
            f_fin    = f_inicio + timedelta(days=random.randint(0, 3))
            doc_aut  = random.choice(docentes) if estado == "aprobada" else None

            cur.execute(
                """
                INSERT INTO justificacion (
                    asistencia_clase_uid, tipo_justificacion, estado_justificacion,
                    padre_solicitante_uid, docente_autorizador_uid,
                    fecha_presentacion, fecha_inicio_incidencia, fecha_fin_incidencia,
                    descripcion_motivo
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING uid
                """,
                (ac_uid, tipo, estado, padre_uid, doc_aut,
                 f_pres, f_inicio, f_fin, random.choice(DESCRIPCIONES)),
            )
            r = cur.fetchone()
            if not r: continue
            just_uid = str(r[0])
            uids.append(just_uid)

            # Actualizar asistencia_clase.justificacion_uid
            cur.execute(
                "UPDATE asistencia_clase SET justificacion_uid = %s WHERE uid = %s",
                (just_uid, ac_uid),
            )

        # Actualizar registro_ingreso para ausencias del mismo día
        # (vincula la primera justificación aprobada del estudiante si existe)
        cur.execute("""
            UPDATE registro_ingreso ri
            SET justificacion_uid = (
                SELECT j.uid FROM justificacion j
                JOIN asistencia_clase ac ON ac.uid = j.asistencia_clase_uid
                WHERE ac.estudiante_uid = ri.estudiante_uid
                  AND ac.fecha_asistencia = ri.fecha_ingreso
                LIMIT 1
            )
            WHERE ri.estado_ingreso = 'ausente'
              AND ri.justificacion_uid IS NULL
        """)
        actualizados_ri = cur.rowcount

        if _local: conn.commit()
        print(f"✅ {len(uids)} justificaciones creadas")
        print(f"   📎 {actualizados_ri} registros_ingreso vinculados con justificacion")
        return uids
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error justificacion: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_justificacion(); sys.exit(0)
