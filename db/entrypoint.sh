#!/bin/bash
set -e

echo "⏳ Esperando a que PostgreSQL esté listo..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
    sleep 2
done
echo "✅ PostgreSQL listo."

echo "🏗️  Creando esquema..."
python schema_creation.py

echo "🌱 Ejecutando seeders..."
python manager.py

echo "✅ Seeding de PostgreSQL completado."