#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN_OVERRIDE:-python3.11}"
fi

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual..."
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Presente estará disponible en http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
