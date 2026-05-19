"""
config.py  — Configuración central del seeder Python
=====================================================
Lee variables de entorno desde el .env raíz del proyecto.

Variables de conexión (.env):
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE

Variables de parametrización (también en .env o como env vars):
    SEED_NUM_DOCENTES       → cuántos docentes faker generar   (default: 12)
    SEED_NUM_AUXILIARES     → cuántos auxiliares faker generar  (default: 3)
    SEED_NUM_ESTUDIANTES    → cuántos estudiantes faker generar (default: 60)
    SEED_NUM_PADRES         → cuántos padres faker generar      (default: 20)
    SEED_NUM_SECCIONES      → cuántas secciones crear           (default: 10)
    SEED_DIAS_HISTORIAL     → días hábiles de registros         (default: 60)
    SEED_PCT_TARDANZA       → % tardanzas en ingreso            (default: 12)
    SEED_PCT_AUSENTE        → % ausencias en ingreso            (default: 8)
"""

import os
from pathlib import Path
import psycopg2
from psycopg2 import pool as pg_pool
from dotenv import load_dotenv

# ── Cargar .env desde raíz del proyecto ───────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)
print(_env_path)
# ── Configuración PostgreSQL ───────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("POSTGRES_HOST",     "localhost"),
    "port":     int(os.getenv("POSTGRES_PORT", "5432")),
    "user":     os.getenv("POSTGRES_USER",     "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "dbname":   os.getenv("POSTGRES_DB", "postgres"),
}

_pool: pg_pool.SimpleConnectionPool | None = None


def get_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.SimpleConnectionPool(1, 5, **DB_CONFIG)
    return _pool


def get_connection() -> psycopg2.extensions.connection:
    return get_pool().getconn()


def release_connection(conn) -> None:
    get_pool().putconn(conn)


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


# ── Parámetros del seeder (100% parametrizables vía env) ─────────────────────
class SeedConfig:
    # ── Volumen de personas ────────────────────────────────────────────────────
    NUM_DOCENTES:    int = int(os.getenv("SEED_NUM_DOCENTES",    "12"))
    NUM_AUXILIARES:  int = int(os.getenv("SEED_NUM_AUXILIARES",  "3"))
    NUM_ESTUDIANTES: int = int(os.getenv("SEED_NUM_ESTUDIANTES", "60"))
    NUM_PADRES:      int = int(os.getenv("SEED_NUM_PADRES",      "20"))

    # ── Estructura académica ───────────────────────────────────────────────────
    NUM_SECCIONES:   int = int(os.getenv("SEED_NUM_SECCIONES",   "10"))

    # ── Historial de asistencia ────────────────────────────────────────────────
    DIAS_HISTORIAL:  int = int(os.getenv("SEED_DIAS_HISTORIAL",  "60"))

    # ── Distribución de estados de ingreso (%) ─────────────────────────────────
    PCT_TARDANZA:    int = int(os.getenv("SEED_PCT_TARDANZA",    "12"))
    PCT_AUSENTE:     int = int(os.getenv("SEED_PCT_AUSENTE",     "8"))
    # El resto se completa con 'a_tiempo'

    # ── Distribución de estados de asistencia_clase (%) ───────────────────────
    PCT_AS_TARDANZA:    int = int(os.getenv("SEED_PCT_AS_TARDANZA",    "8"))
    PCT_AS_FALTA:       int = int(os.getenv("SEED_PCT_AS_FALTA",       "5"))
    PCT_AS_JUSTIFICADA: int = int(os.getenv("SEED_PCT_AS_JUSTIFICADA", "2"))
    # El resto se completa con 'presente'

    # ── Credencial de prueba ───────────────────────────────────────────────────
    DEFAULT_HASH: str = "$2b$10$fixedHashForTestingPurposesOnly.xyz"

    # ── Usuarios reales del equipo (hardcodeados) ──────────────────────────────
    ADMIN_USUARIOS: list[dict] = [
        {"email": "emamania1@upao.edu.pe", "rol": "admin"},
        {"email": "gmerinop1@upao.edu.pe", "rol": "admin"},
    ]

    @classmethod
    def print_resumen(cls) -> None:
        print("📋 Parámetros del seeder:")
        print(f"   Docentes:       {cls.NUM_DOCENTES}")
        print(f"   Auxiliares:     {cls.NUM_AUXILIARES}")
        print(f"   Estudiantes:    {cls.NUM_ESTUDIANTES}")
        print(f"   Padres:         {cls.NUM_PADRES}")
        print(f"   Secciones:      {cls.NUM_SECCIONES}")
        print(f"   Días historial: {cls.DIAS_HISTORIAL}")
        print(f"   % Tardanza:     {cls.PCT_TARDANZA}%")
        print(f"   % Ausente:      {cls.PCT_AUSENTE}%")
