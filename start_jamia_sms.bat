@echo off
TITLE Jamia SMS - One-Click Launcher
COLOR 0A

echo =====================================================================
echo   JAMIA HAMDARD - SEST - DEPARTMENT OF COMPUTER SCIENCE & ENG.
echo   Academic Record, Result & Attendance Management System (jamia_sms)
echo   Capstone Project-II (BTCSE 701) | Dec 18 Viva Ready
echo =====================================================================
echo.
echo Starting all 3 microservices in separate windows...
echo.

:: 1. Launch FastAPI Backend
echo [1/3] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "Jamia SMS - 1. FastAPI Backend (Port 8000)" cmd /k "title Jamia SMS - FastAPI Backend && cd /d %~dp0 && color 0B && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: Wait 2 seconds for backend to initialize
timeout /t 2 /nobreak >nul

:: 2. Launch Streamlit Frontend
echo [2/3] Launching Streamlit Portal on http://localhost:8501 ...
start "Jamia SMS - 2. Streamlit Web Portal (Port 8501)" cmd /k "title Jamia SMS - Streamlit Portal && cd /d %~dp0 && color 0E && python -m streamlit run app.py --server.port 8501"

:: Wait 2 seconds
timeout /t 2 /nobreak >nul

:: 3. Launch ngrok Reverse Tunnel
echo [3/3] Launching ngrok Public Webhook Tunnel ...
start "Jamia SMS - 3. ngrok Webhook Tunnel" cmd /k "title Jamia SMS - ngrok Tunnel && color 0D && ngrok http 8000 --url=unstuck-cosigner-roving.ngrok-free.dev"

echo.
echo =====================================================================
echo   ALL 3 SERVICES LAUNCHED SUCCESSFULLY!
echo.
echo   - Backend Swagger Docs : http://localhost:8000/docs
echo   - Streamlit Dashboard  : http://localhost:8501
echo   - Public ngrok URL     : https://unstuck-cosigner-roving.ngrok-free.dev
echo   - WhatsApp Webhook     : https://unstuck-cosigner-roving.ngrok-free.dev/webhook/whatsapp
echo.
echo   To STOP all services, run stop_jamia_sms.bat or press Ctrl+C in each window.
echo =====================================================================
echo.
pause
