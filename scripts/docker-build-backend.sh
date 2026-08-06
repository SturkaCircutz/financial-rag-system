#!/usr/bin/env bash
set -euo pipefail

image_name="${1:-financial-rag-backend:local}"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to build the backend image."
  exit 127
fi

docker build -t "$image_name" "$repo_root/backend"
