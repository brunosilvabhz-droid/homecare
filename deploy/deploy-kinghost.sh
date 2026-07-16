#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/impacto-care}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/impacto-care}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.kinghost.yml)

cd "$APP_DIR"
test -f .env || { echo "ERRO: $APP_DIR/.env não existe." >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"

echo "[1/7] Validando a configuração atual"
"${COMPOSE[@]}" config --quiet

echo "[2/7] Criando backup do PostgreSQL"
"${COMPOSE[@]}" exec -T db pg_dump \
  -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2-)" \
  -d "$(grep '^POSTGRES_DB=' .env | cut -d= -f2-)" \
  -Fc > "$BACKUP_DIR/impacto-care-$timestamp.dump"

echo "[3/7] Atualizando o código"
git pull --ff-only origin main

echo "[4/7] Validando a nova configuração"
"${COMPOSE[@]}" config --quiet

echo "[5/7] Construindo e iniciando os serviços"
"${COMPOSE[@]}" up -d --build --remove-orphans

echo "[6/7] Conferindo containers e migrações"
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" exec -T api alembic current

echo "[7/7] Verificando a API e o frontend"
curl --fail --silent --show-error --retry 12 --retry-delay 5 http://127.0.0.1:8010/health
curl --fail --silent --show-error --head --retry 12 --retry-delay 5 http://127.0.0.1:5180 >/dev/null

echo "Deploy concluído. Backup: $BACKUP_DIR/impacto-care-$timestamp.dump"
