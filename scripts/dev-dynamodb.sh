#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DYNAMODB_PORT="${DYNAMODB_LOCAL_PORT:-8000}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run DynamoDB Local."
  exit 127
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required to run DynamoDB Local."
  exit 127
fi

cd "$REPO_ROOT"
"${COMPOSE[@]}" up -d dynamodb-local

export REPORTS_DYNAMODB_ENDPOINT_URL="${REPORTS_DYNAMODB_ENDPOINT_URL:-http://localhost:$DYNAMODB_PORT}"
export REPORTS_DYNAMODB_TABLE_NAME="${REPORTS_DYNAMODB_TABLE_NAME:-financial-rag}"
export REPORT_REPOSITORY_MODE="${REPORT_REPOSITORY_MODE:-dynamodb}"
export REPORT_QUEUE_MODE="${REPORT_QUEUE_MODE:-memory}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"
export AWS_EC2_METADATA_DISABLED="${AWS_EC2_METADATA_DISABLED:-true}"

"$SCRIPT_DIR/deploy-dynamodb.sh"
exec "$SCRIPT_DIR/dev.sh"
