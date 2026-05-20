"""
api/app/db.py — Conexión dinámica a PostgreSQL para la API FastAPI.
==================================================================
Soporta de forma flexible las dos configuraciones del proyecto:
1. PG_* (usadas por el modulo de seeders en db/config.py)
2. POSTGRES_* (definidas en .env.example y docker-compose.yml)

De esta forma no obligamos a usar un esquema rígido ni hardcodeamos datos.
"""
import os
from pathlib import Path
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto si existe
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

# Resolución dinámica de variables para evitar hardcoding
DB_CONFIG = {
    "host":     os.getenv("PG_HOST") or os.getenv("POSTGRES_HOST") or "localhost",
    "port":     int(os.getenv("PG_PORT") or os.getenv("POSTGRES_PORT") or "5432"),
    "user":     os.getenv("PG_USER") or os.getenv("POSTGRES_USER") or "postgres",
    "password": os.getenv("PG_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or "",
    "dbname":   os.getenv("PG_DATABASE") or os.getenv("POSTGRES_DB") or "postgres",
}

_pool: pg_pool.SimpleConnectionPool | None = None


def _obtener_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.SimpleConnectionPool(1, 15, **DB_CONFIG)
    return _pool



@contextmanager
def db_cursor(dict_cursor: bool = True):
    """
    Context manager que provee un cursor listo para interactuar con la BD.
    Realiza commit automático si no hay excepciones; rollback si ocurre algún error.
    """
    pool = _obtener_pool()
    conn = pool.getconn()
    factory = RealDictCursor if dict_cursor else None
    cur = conn.cursor(cursor_factory=factory)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        pool.putconn(conn)
