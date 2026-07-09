@echo off
title IK Tracker - Backend
cd /d "%~dp0backend"
echo Backend: http://localhost:8000  (docs: /docs)
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo Backend остановлен. Закройте окно или нажмите любую клавишу.
pause >nul
