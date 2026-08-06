#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

if ! command -v mvn >/dev/null 2>&1; then
  echo "mvn is required to run backend checks. Install Maven 3.9+ or add Maven to PATH."
  exit 127
fi

mvn test
