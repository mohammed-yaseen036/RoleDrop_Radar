@echo off
title RoleDrop Radar Orchestrator
echo ==============================================
echo   Starting RoleDrop Radar Development Environment
echo ==============================================
echo.

:: Start Backend in a new window
echo [SYSTEM] Starting FastAPI Backend on http://localhost:8000...
start "RoleDrop Radar - Backend Server" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"

:: Start Frontend in the current window
echo [SYSTEM] Starting Vite React Frontend on http://localhost:5173...
echo.
cd frontend
npm run dev

pause
