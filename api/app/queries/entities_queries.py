import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "mysecretpassword"),
        dbname=os.getenv("POSTGRES_DB", "defaultdb")
    )

def query_get_estudiantes() -> List[Dict[str, Any]]:
    """Obtiene la lista real de estudiantes desde la base de datos."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT e.uid, e.nombres, e.apellidos, u.email, e.rekognition_face_id
                FROM estudiante e
                JOIN usuario u ON e.uid = u.uid
                WHERE u.activo = true;
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
        

def query_get_cursos() -> List[Dict[str, Any]]:
    """Obtiene la lista de cursos desde la base de datos."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT uid, nombre, codigo
                FROM curso;
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def query_get_profesores() -> List[Dict[str, Any]]:
    """Obtiene la lista de profesores (docentes) desde la base de datos."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT d.uid, d.nombres, d.apellidos, u.email, c.nombre as especialidad
                FROM docente d
                JOIN usuario u ON d.uid = u.uid
                LEFT JOIN curso c ON d.curso_especialidad_uid = c.uid
                WHERE u.activo = true;
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
