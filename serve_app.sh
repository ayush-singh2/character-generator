#!/usr/bin/env bash
# Boot the BB-artists app (FastAPI backend + the design pages).
# Open http://localhost:8000/Login.html
set -euo pipefail
cd "$(dirname "$0")"

VENV="${VENV:-.venv}"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

exec "$VENV/bin/uvicorn" server.app:app --host "$HOST" --port "$PORT" "${@:---reload}"
