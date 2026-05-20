"""
seeds/asistencia.py
====================
Genera los registros de asistencia (todo UUID en v3).

TABLAS:
  1. registro_ingreso  — control matutino (1 por alumno por día hábil)
  2. asistencia_clase  — control por clase (1 por alumno × horario × día)

DISTRIBUCIÓN (parametrizable en SeedConfig):
  registro_ingreso:
    a_tiempo = 100 - PCT_TARDANZA - PCT_AUSENTE
    tardanza = PCT_TARDANZA   (default 12%)
    ausente  = PCT_AUSENTE    (default  8%)

  asistencia_clase:
    presente   = 100 - PCT_AS_TARDANZA - PCT_AS_FALTA - PCT_AS_JUSTIFICADA
    tardanza   = PCT_AS_TARDANZA   (default 8%)
    falta      = PCT_AS_FALTA      (default 5%)
    justificada= PCT_AS_JUSTIFICADA (default 2%)

NOTA: justificacion_uid se deja NULL aquí. El seeder justificacion.py
lo rellena después con UPDATE.
"""
import sys
import random
from datetime import date, datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool, SeedConfig



def _dias_habiles(inicio: date, cantidad: int) -> list[date]:
    """Genera `cantidad` días L-V a partir de `inicio`."""
    dias, d = [], inicio
    while len(dias) < cantidad:
        if d.weekday() < 5: dias.append(d)
        d += timedelta(days=1)
    return dias


def _build_pool(total: int, pct_b: int, pct_c: int,
                val_a: str, val_b: str, val_c: str) -> list[str]:
    """Construye lista de estados con porcentajes exactos."""
    n_b = pct_b; n_c = pct_c; n_a = total - n_b - n_c
    return [val_a]*n_a + [val_b]*n_b + [val_c]*n_c


# ─────────────────────────────────────────────────────────────────────────────
def seed_registro_ingreso(conn=None) -> int:
    """1 registro por alumno por día hábil. Retorna cantidad insertada."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding registro_ingreso...")

        cur.execute("""
            SELECT m.uid, m.estudiante_uid
            FROM matricula m
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE AND m.estado_matricula = 'activa'
        """)
        matriculas = [(str(r[0]), str(r[1])) for r in cur.fetchall()]

        cur.execute("SELECT uid FROM auxiliar LIMIT 1")
        r = cur.fetchone()
        aux_uid = str(r[0]) if r else None

        inicio = date(2025, 3, 3) + timedelta(days=1)
        dias   = _dias_habiles(inicio, SeedConfig.DIAS_HISTORIAL)

        ESTADOS = _build_pool(
            100, SeedConfig.PCT_TARDANZA, SeedConfig.PCT_AUSENTE,
            "a_tiempo", "tardanza", "ausente"
        )

        insertados = 0
        BATCH = 300

        for mat_uid, est_uid in matriculas:
            rows = []
            for d in dias:
                estado = random.choice(ESTADOS)
                hora = datetime(d.year, d.month, d.day,
                                7, random.randint(15, 59),
                                random.randint(0, 59))
                rows.append((mat_uid, est_uid, aux_uid, d, hora, estado))

            for i in range(0, len(rows), BATCH):
                for row in rows[i:i+BATCH]:
                    try:
                        cur.execute(
                            """
                            INSERT INTO registro_ingreso
                                (matricula_uid, estudiante_uid, auxiliar_receptor_uid,
                                 fecha_ingreso, hora_llegada, estado_ingreso)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (matricula_uid, fecha_ingreso) DO NOTHING
                            """,
                            row,
                        )
                        insertados += cur.rowcount
                    except Exception:
                        conn.rollback()
                conn.commit()

        print(f"✅ {insertados} registros de ingreso insertados")
        return insertados
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error registro_ingreso: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


# ─────────────────────────────────────────────────────────────────────────────
def seed_asistencia_clase(conn=None) -> int:
    """
    1 registro por alumno × horario × día hábil.
    justificacion_uid = NULL (se rellena en seed_justificacion).
    Retorna cantidad insertada.
    """
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding asistencia_clase...")

        cur.execute("""
            SELECT m.uid, m.estudiante_uid, m.seccion_uid
            FROM matricula m
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE AND m.estado_matricula = 'activa'
        """)
        matriculas = [(str(r[0]), str(r[1]), str(r[2])) for r in cur.fetchall()]

        cur.execute("""
            SELECT seccion_uid, uid, dia_semana, docente_dictante_uid
            FROM horario_clase
        """)
        hor_por_sec: dict[str, list] = {}
        for sec_uid, h_uid, dia, doc_uid in cur.fetchall():
            hor_por_sec.setdefault(str(sec_uid), []).append(
                (str(h_uid), dia, str(doc_uid))
            )

        inicio = date(2025, 3, 3) + timedelta(days=1)
        dias   = _dias_habiles(inicio, SeedConfig.DIAS_HISTORIAL)
        DIA_WD = {"lunes":0,"martes":1,"miercoles":2,"jueves":3,"viernes":4}

        ESTADOS = _build_pool(
            100,
            SeedConfig.PCT_AS_TARDANZA,
            SeedConfig.PCT_AS_FALTA,
            "presente", "tardanza", "falta",
        )
        # Agregar justificada separado
        PCT_JUST = SeedConfig.PCT_AS_JUSTIFICADA

        insertados = 0
        for mat_uid, est_uid, sec_uid in matriculas:
            horarios = hor_por_sec.get(sec_uid, [])
            if not horarios: continue

            for d in dias:
                dia_nom = list(DIA_WD.keys())[d.weekday()]
                clases  = [(h, doc) for h, dia, doc in horarios if dia == dia_nom]

                for h_uid, doc_uid in clases:
                    # Pequeña probabilidad de justificada (reemplaza estado)
                    if random.randint(1, 100) <= PCT_JUST:
                        estado = "justificada"
                    else:
                        estado = random.choice(ESTADOS)

                    try:
                        cur.execute(
                            """
                            INSERT INTO asistencia_clase
                                (matricula_uid, estudiante_uid, horario_clase_uid,
                                 fecha_asistencia, estado_asistencia,
                                 docente_controlador_uid)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (matricula_uid, horario_clase_uid, fecha_asistencia)
                            DO NOTHING
                            """,
                            (mat_uid, est_uid, h_uid, d, estado, doc_uid),
                        )
                        insertados += cur.rowcount
                    except Exception:
                        conn.rollback()

            conn.commit()  # commit por alumno

        print(f"✅ {insertados} registros de asistencia_clase insertados")
        return insertados
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error asistencia_clase: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_registro_ingreso()
    seed_asistencia_clase()
    sys.exit(0)
