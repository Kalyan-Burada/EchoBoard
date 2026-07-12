@echo off
echo === EchoBoard Dataset Creation Module ===
echo Starting FastAPI backend...
cd /d "%~dp0\.."
python -m uvicorn backend.api:app --reload --port 8000
pause
