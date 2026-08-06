#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT/rag-service"

if [ -z "${PYTHON_BIN:-}" ] && [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

PYTHONPATH="$REPO_ROOT/rag-service/src" "$PYTHON_BIN" -m rag_service.operations_cli reindex "$@"
