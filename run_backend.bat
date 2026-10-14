@echo off
title HydraControl Backend Server
echo Starting HydraControl High-Performance Backend...
call .\venv\Scripts\activate.bat
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend --app-dir backend
pause
