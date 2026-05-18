"""
config.py
=========
Configuración centralizada del seeder Python.
Lee variables de entorno desde el .env raíz del proyecto.
Usa psycopg2 como driver PostgreSQL (equivalente a node-postgres).

Parámetros configurables vía .env:
  PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE

Parámetros del seeder (cuántos registros generar):
  SEED_NUM_DOCENTES       (default: 15)
  SEED_NUM_AUXILIARES     (default: 3)
  SEED_NUM_ESTUDIANTES    (default: 80)
  SEED_NUM_PADRES         (default: 20)
  SEED_NUM_SECCIONES      (default: 10)
  SEED_NUM_DIAS_HISTORIAL (default: 60)  ← días de registros de asistencia
"""

import os
from pathlib import Path
import psycopg2
from psycopg2 import pool as pg_pool
from dotenv import load_dotenv

# ── Cargar .env desde la raíz del proyecto (un nivel arriba) ──────────────────
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# ── Conexión PostgreSQL ───────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("PG_HOST",     "localhost"),
    "port":     int(os.getenv("PG_PORT", "5432")),
    "user":     os.getenv("PG_USER",     "postgres"),
    "password": os.getenv("PG_PASSWORD", ""),
    "dbname":   os.getenv("PG_DATABASE", "asistencia_colegio"),
}

# Pool de conexiones (min 1, max 5 para seeders secuenciales)
_connection_pool: pg_pool.SimpleConnectionPool | None = None


def get_pool() -> pg_pool.SimpleConnectionPool:
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pg_pool.SimpleConnectionPool(1, 5, **DB_CONFIG)
    return _connection_pool


def get_connection() -> psycopg2.extensions.connection:
    """Obtiene una conexión del pool. Llamar conn.close() al terminar."""
    return get_pool().getconn()


def release_connection(conn: psycopg2.extensions.connection) -> None:
    get_pool().putconn(conn)


def close_pool() -> None:
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None


# ── Parámetros del seeder (completamente parametrizables) ────────────────────
class SeedConfig:
    """
    Todos los contadores de registros a generar.
    Modifica estos valores o pásalos como variables de entorno
    para ajustar el volumen de datos.
    """
    # Personas
    NUM_DOCENTES:       int = int(os.getenv("SEED_NUM_DOCENTES",       "15"))
    NUM_AUXILIARES:     int = int(os.getenv("SEED_NUM_AUXILIARES",     "3"))
    NUM_ESTUDIANTES:    int = int(os.getenv("SEED_NUM_ESTUDIANTES",    "80"))
    NUM_PADRES:         int = int(os.getenv("SEED_NUM_PADRES",         "20"))

    # Estructura académica
    NUM_SECCIONES:      int = int(os.getenv("SEED_NUM_SECCIONES",      "10"))
    NUM_CURSOS:         int = int(os.getenv("SEED_NUM_CURSOS",         "12"))

    # Historial de asistencia
    DIAS_HISTORIAL:     int = int(os.getenv("SEED_NUM_DIAS_HISTORIAL", "60"))

    # Hash fijo para todos los usuarios de prueba (contraseña: password123)
    DEFAULT_HASH: str = "$2b$10$fixedHashForTestingPurposesOnly123456789"

    # Equipo real (2 admins hardcodeados)
    ADMIN_USUARIOS: list[dict] = [
        {"email": "emamania1@upao.edu.pe",  "rol": "admin"},
        {"email": "gmerinop1@upao.edu.pe",  "rol": "admin"},
    ]

    @classmethod
    def resumen(cls) -> str:
        lines = [
            "📋 Configuración del Seeder:",
            f"   • Docentes:       {cls.NUM_DOCENTES}",
            f"   • Auxiliares:     {cls.NUM_AUXILIARES}",
            f"   • Estudiantes:    {cls.NUM_ESTUDIANTES}",
            f"   • Padres:         {cls.NUM_PADRES}",
            f"   • Secciones:      {cls.NUM_SECCIONES}",
            f"   • Días historial: {cls.DIAS_HISTORIAL}",
        ]
        return "\n".join(lines)
