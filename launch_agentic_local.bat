@echo off
setlocal

REM RTGS Agentic local launcher for Windows
REM Starts frontend on :3000 and FastAPI backend on :8000

cd /d %~dp0

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo Python not found in PATH. Install Python 3.10+ and retry.
  exit /b 1
)

echo [2/3] Checking backend dependencies...
python -c "import importlib.util,sys;missing=[m for m in ['fastapi','uvicorn'] if importlib.util.find_spec(m) is None];print('missing:',missing);sys.exit(1 if missing else 0)"
if errorlevel 1 (
  echo Missing packages. Install with:
  echo python -m pip install fastapi uvicorn pydantic scikit-learn
  exit /b 1
)

echo [3/3] Launching services...
start "RTGS Frontend :3000" cmd /k "cd /d %~dp0 && python -m http.server 3000 --directory frontend"
start "RTGS API :8000" cmd /k "cd /d %~dp0 && python -m uvicorn rtgs_fastapi_app:app --host 0.0.0.0 --port 8000"

echo.
echo Frontend: http://localhost:3000
echo API:      http://localhost:8000
echo.
echo If localhost still refuses connection, open the 2 new terminal windows and check for dependency errors.

endlocal
