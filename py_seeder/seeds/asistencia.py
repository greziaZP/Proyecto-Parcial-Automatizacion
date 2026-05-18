"""
seeds/asistencia.py
===================
Genera los registros de asistencia para el historial de días configurado.

TABLAS que puebla:
  1. registro_ingreso  — control matutino del auxiliar (1 por alumno por día)
  2. asistencia_clase  — control del docente por clase (1 por alumno por horario por día)

Distribución realista (ajustable vía SeedConfig):
  registro_ingreso:
    80% a_tiempo | 12% tardanza | 8% ausente

  asistencia_clase:
    85% presente | 8% tardanza | 5% falta | 2% justificada

Solo procesa días de lunes a viernes.
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import random
from datetime import date, timedelta
from config import get_connection, release_connection, close_pool, SeedConfig


def _dias_habiles(inicio: date, cantidad: int) -> list[date]:
    """Genera `cantidad` días hábiles (L-V) a partir de `inicio`."""
    dias = []
    d = inicio
    while len(dias) < cantidad:
        if d.weekday() < 5:  # 0=lunes ... 4=viernes
            dias.append(d)
        d += timedelta(days=1)
    return dias


# ─────────────────────────────────────────────────────────────────────────────
def seed_registro_ingreso(conn=None) -> None:
    """
    Genera 1 registro de ingreso por alumno por día hábil.
    Distribución: 80% a_tiempo, 12% tardanza, 8% ausente.
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding registro_ingreso...")

        # Obtener matrículas activas del año activo con datos del auxiliar
        cur.execute("""
            SELECT m.uid, m.estudiante_uid
            FROM matricula m
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE AND m.estado_matricula = 'activa'
        """)
        matriculas = cur.fetchall()  # [(mat_uid, est_uid), ...]

        cur.execute("SELECT uid FROM auxiliar LIMIT 1")
        row = cur.fetchone()
        auxiliar_uid = str(row[0]) if row else None

        # Fecha base: 60 días hábiles atrás desde hoy
        inicio = date.today() - timedelta(days=SeedConfig.DIAS_HISTORIAL * 1.5)
        dias = _dias_habiles(inicio, SeedConfig.DIAS_HISTORIAL)

        ESTADOS = ["a_tiempo"] * 80 + ["tardanza"] * 12 + ["ausente"] * 8

        batch = []
        for mat_uid, est_uid in matriculas:
            for dia in dias:
                estado = random.choice(ESTADOS)
                if estado == "ausente":
                    hora_llegada_ts = None
                else:
                    # Hora de llegada entre 07:15 y 08:00 (Peru UTC-5)
                    minutos_extra = random.randint(0, 45)
                    hora_llegada_ts = f"{dia}T07:{15 + minutos_extra:02d}:00-05:00"

                batch.append((
                    str(mat_uid), str(est_uid), auxiliar_uid,
                    dia, hora_llegada_ts or f"{dia}T07:30:00-05:00",
                    estado,
                ))

        # Insertar en lotes de 500
        LOTE = 500
        insertados = 0
        for i in range(0, len(batch), LOTE):
            lote = batch[i:i + LOTE]
            for row in lote:
                try:
                    cur.execute(
                        """
                        INSERT INTO registro_ingreso
                            (matricula_uid, estudiante_uid, auxiliar_receptor_uid,
                             fecha_ingreso, hora_llegada, estado_ingreso)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (matricula_uid, fecha_ingreso) DO NOTHING
                        """,
                        row,
                    )
                    insertados += cur.rowcount
                except Exception:
                    conn.rollback()

            conn.commit()
            print(f"   ... {min(i + LOTE, len(batch))}/{len(batch)} procesados", end="\r")

        print(f"\n✅ {insertados} registros de ingreso insertados")

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding registro_ingreso: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_asistencia_clase(conn=None) -> None:
    """
    Genera 1 registro de asistencia_clase por alumno por horario por día hábil.
    Distribución: 85% presente | 8% tardanza | 5% falta | 2% justificada.
    """
    _local = conn is None
    if _local:
        conn = get_connection()
    cur = conn.cursor()

    try:
        print("🌱 Seeding asistencia_clase...")

        # Matrículas activas con sección y horarios
        cur.execute("""
            SELECT m.uid, m.estudiante_uid, m.seccion_uid
            FROM matricula m
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE AND m.estado_matricula = 'activa'
        """)
        matriculas = cur.fetchall()

        # Horarios por sección: {sec_uid: [(h_uid, dia, docente_uid), ...]}
        cur.execute("""
            SELECT seccion_uid, uid, dia_semana, docente_dictante_uid
            FROM horario_clase
        """)
        horarios_por_sec: dict[str, list] = {}
        for sec_uid, h_uid, dia, doc_uid in cur.fetchall():
            sec_uid = str(sec_uid)
            horarios_por_sec.setdefault(sec_uid, []).append(
                (str(h_uid), dia, str(doc_uid))
            )

        inicio = date.today() - timedelta(days=SeedConfig.DIAS_HISTORIAL * 1.5)
        dias = _dias_habiles(inicio, SeedConfig.DIAS_HISTORIAL)

        # Mapa dia_nombre → weekday index
        DIA_WEEKDAY = {
            "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4
        }

        ESTADOS = (
            ["presente"] * 85 + ["tardanza"] * 8
            + ["falta"] * 5 + ["justificada"] * 2
        )

        insertados = 0
        total_esperado = 0

        for mat_uid, est_uid, sec_uid in matriculas:
            mat_uid, est_uid, sec_uid = str(mat_uid), str(est_uid), str(sec_uid)
            horarios = horarios_por_sec.get(sec_uid, [])
            if not horarios:
                continue

            for dia_fecha in dias:
                # Filtrar horarios del día de la semana
                dia_nombre = list(DIA_WEEKDAY.keys())[dia_fecha.weekday()]
                clases_hoy = [(h, d, doc) for h, d, doc in horarios if d == dia_nombre]

                for h_uid, _, doc_uid in clases_hoy:
                    total_esperado += 1
                    estado = random.choice(ESTADOS)
                    try:
                        cur.execute(
                            """
                            INSERT INTO asistencia_clase
                                (matricula_uid, estudiante_uid, horario_clase_uid,
                                 fecha_asistencia, estado_asistencia,
                                 docente_controlador_uid)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (matricula_uid, horario_clase_uid, fecha_asistencia)
                            DO NOTHING
                            """,
                            (mat_uid, est_uid, h_uid, dia_fecha, estado, doc_uid),
                        )
                        insertados += cur.rowcount
                    except Exception:
                        conn.rollback()

            # Commit por alumno para no acumular demasiado en memoria
            conn.commit()

        print(f"✅ {insertados}/{total_esperado} registros de asistencia_clase insertados")

    except Exception as e:
        if _local:
            conn.rollback()
        print(f"❌ Error seeding asistencia_clase: {e}")
        raise
    finally:
        cur.close()
        if _local:
            release_connection(conn)
            close_pool()


if __name__ == "__main__":
    seed_registro_ingreso()
    seed_asistencia_clase()
