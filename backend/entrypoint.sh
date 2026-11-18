#!/bin/sh
set -e

echo "[GERAT] Executando migrações Alembic..."
alembic upgrade head

echo "[GERAT] Iniciando servidor API..."
exec "$@"
