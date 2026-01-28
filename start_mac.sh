#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8090}"
DB_FILE="${2:-app.db}"

export APP_DB_FILE="$DB_FILE"
if [[ -f "requirements.txt" ]]; then
  echo "Checking dependencies in requirements.txt..."
  python3 -m pip install -r requirements.txt
else
  echo "requirements.txt not found, skip dependency install."
fi
echo "Starting API on port ${PORT} using ${DB_FILE}"

exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}"
