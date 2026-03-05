#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[1/3] Checking Python..."
python --version

echo "[2/3] Checking backend dependencies..."
if ! python - <<'PY'
import importlib.util
mods=['fastapi','uvicorn']
missing=[m for m in mods if importlib.util.find_spec(m) is None]
print('MISSING:'+','.join(missing) if missing else 'OK')
raise SystemExit(1 if missing else 0)
PY
then
  echo "Missing Python packages (fastapi/uvicorn)."
  echo "Install manually with: python -m pip install fastapi uvicorn pydantic scikit-learn"
  exit 1
fi

echo "[3/3] Launching services..."
python -m http.server 3000 --directory frontend >/tmp/rtgs_frontend.log 2>&1 &
FRONT_PID=$!
python -m uvicorn rtgs_fastapi_app:app --host 0.0.0.0 --port 8000 >/tmp/rtgs_api.log 2>&1 &
API_PID=$!

echo "Frontend: http://localhost:3000 (pid ${FRONT_PID})"
echo "API:      http://localhost:8000 (pid ${API_PID})"
echo "Logs: /tmp/rtgs_frontend.log, /tmp/rtgs_api.log"
