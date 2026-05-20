import random
from faker import Faker
from config import get_connection, release_connection

fake = Faker('es_ES')

def seed_citacion() -> None:
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Obtenemos algunos estudiantes que tengan padre asociado
        cur.execute("""
            SELECT e.uid, r.padre_apoderado_uid 
            FROM estudiante e
            JOIN relacion_padre_estudiante r ON e.uid = r.estudiante_uid
            LIMIT 20;
        """)
        estudiantes_padres = cur.fetchall()

        if not estudiantes_padres:
            print("⚠️ citacion => No hay estudiantes con padre para crear citaciones.")
            return

        # Obtenemos TODOS los docentes
        cur.execute("SELECT uid FROM docente;")
        docentes = [r[0] for r in cur.fetchall()]

        if not docentes:
            print("⚠️ citacion => No hay docentes para crear citaciones.")
            return

        motivos = [
            "Reincidencia de tardanzas en horario de ingreso.",
            "Comportamiento inadecuado repetitivo en el aula.",
            "Bajo rendimiento académico y ausencias injustificadas.",
            "Faltas de respeto a compañeros y/o plana docente.",
            "No asiste a las actividades extracurriculares obligatorias."
        ]
        niveles_urgencia = ["baja", "media", "alta"]
        estados = ["programada", "completada", "cancelada", "reprogramada"]

        num_creados = 0
        for estudiante_uid, padre_uid in estudiantes_padres:
            # Crear 1 o 2 citaciones por estudiante
            for _ in range(random.randint(1, 2)):
                docente_uid = random.choice(docentes)
                motivo = random.choice(motivos)
                urgencia = random.choice(niveles_urgencia)
                estado = random.choice(estados)
                fecha_citacion = fake.date_time_between(start_date='-30d', end_date='+15d')

                cur.execute("""
                    INSERT INTO citacion (
                        estudiante_uid,
                        padre_apoderado_uid,
                        docente_solicitante_uid,
                        motivo,
                        nivel_urgencia,
                        estado,
                        fecha_citacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    estudiante_uid, padre_uid, docente_uid,
                    motivo, urgencia, estado, fecha_citacion
                ))
                num_creados += 1

        conn.commit()
        print(f"✅ citacion => insertadas {num_creados} filas faker.")

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        release_connection(conn)
