"""
seeds/nota_actitudinal.py — Notas actitudinales por alumno × período (UUID PK).

Fórmula:
    calificacion = MAX(0, 20 - tardanzas×0.5 - inasistencias×1.0 - fugas×1.5)

Una fila por (matricula_uid, periodo_uid). Estado = 'publicado' al calcular.
"""
import sys
import random
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_connection, release_connection, close_pool


def seed_nota_actitudinal(conn=None) -> int:
    """Calcula e inserta notas actitudinales. Retorna filas insertadas."""
    _local = conn is None
    if _local: conn = get_connection()
    cur = conn.cursor()
    try:
        print("🌱 Seeding notas actitudinales...")

        # Matrículas activas del año activo
        cur.execute("""
            SELECT m.uid, m.estudiante_uid
            FROM matricula m
            JOIN seccion s ON s.uid = m.seccion_uid
            JOIN ano_escolar a ON a.uid = s.ano_escolar_uid
            WHERE a.activo = TRUE AND m.estado_matricula = 'activa'
        """)
        matriculas = [(str(r[0]), str(r[1])) for r in cur.fetchall()]

        # Períodos del año activo
        cur.execute("""
            SELECT pt.uid FROM periodo_trimestral pt
            JOIN ano_escolar a ON a.uid = pt.ano_escolar_uid
            WHERE a.activo = TRUE
            ORDER BY pt.numero_trimestre
        """)
        periodos = [str(r[0]) for r in cur.fetchall()]
        if not periodos:
            raise ValueError("No hay períodos trimestrales para el año activo.")

        # Docentes para docente_evaluador_uid
        cur.execute("SELECT uid FROM docente")
        docentes = [str(r[0]) for r in cur.fetchall()]

        insertados = 0

        for mat_uid, est_uid in matriculas:
            for per_uid in periodos:
                # Contar tardanzas NO justificadas en asistencia_clase
                cur.execute("""
                    SELECT COUNT(*) FROM asistencia_clase
                    WHERE matricula_uid = %s
                      AND estado_asistencia = 'tardanza'
                      AND justificacion_uid IS NULL
                """, (mat_uid,))
                tard = int(cur.fetchone()[0])

                # Contar inasistencias (falta) NO justificadas
                cur.execute("""
                    SELECT COUNT(*) FROM asistencia_clase
                    WHERE matricula_uid = %s
                      AND estado_asistencia = 'falta'
                      AND justificacion_uid IS NULL
                """, (mat_uid,))
                inas = int(cur.fetchone()[0])

                # Contar fugas relacionadas a esta matrícula
                cur.execute("""
                    SELECT COUNT(*) FROM fuga f
                    JOIN asistencia_clase ac ON ac.uid = f.asistencia_clase_uid
                    WHERE ac.matricula_uid = %s
                      AND f.estado_fuga IN ('detectada','notificada')
                """, (mat_uid,))
                fugas = int(cur.fetchone()[0])

                # Fórmula de calificación
                calif_raw = 20 - (tard * 0.5) - (inas * 1.0) - (fugas * 1.5)
                calif = max(Decimal("0.00"), Decimal(str(calif_raw)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ))

                # Promedio académico simulado (dato externo)
                promed = Decimal(str(round(random.uniform(11.0, 20.0), 2)))

                doc_eval = random.choice(docentes) if docentes else None

                cur.execute(
                    """
                    INSERT INTO nota_actitudinal (
                        matricula_uid, periodo_uid,
                        total_tardanzas, total_inasistencias, total_fugas,
                        calificacion_valor, promedio_academico,
                        estado_reporte, docente_evaluador_uid
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'publicado',%s)
                    ON CONFLICT (matricula_uid, periodo_uid) DO NOTHING
                    """,
                    (mat_uid, per_uid, tard, inas, fugas,
                     calif, promed, doc_eval),
                )
                insertados += cur.rowcount

            # Commit cada alumno para no acumular
            conn.commit()

        print(f"✅ {insertados} notas actitudinales insertadas")
        return insertados
    except Exception as e:
        if _local: conn.rollback()
        print(f"❌ Error nota_actitudinal: {e}"); raise
    finally:
        cur.close()
        if _local: release_connection(conn); close_pool()


if __name__ == "__main__":
    seed_nota_actitudinal(); sys.exit(0)
