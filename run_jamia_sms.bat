@echo off
title Jamia Hamdard SMS Launcher
echo ===================================================
echo Starting Jamia Hamdard Academic Management System
echo ===================================================

cd /d "%~dp0"

echo 1. Launching FastAPI Backend (Port 8000)...
start "FastAPI Backend" cmd /k "python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 2 >nul

echo 2. Launching Streamlit Frontend (Port 8501)...
start "Streamlit Portal" cmd /k "python -m streamlit run app.py --server.port 8501"

timeout /t 3 >nul

echo 3. Opening Browser...
start http://localhost:8501

echo.
echo All services launched! You can minimize these windows.
echo To stop the system later, simply close the opened terminal windows.
