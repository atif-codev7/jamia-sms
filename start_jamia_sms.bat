@echo off
TITLE Jamia SMS - One-Click Launcher
COLOR 0A

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo =====================================================================
echo   JAMIA HAMDARD - SEST - DEPARTMENT OF COMPUTER SCIENCE AND ENG.
echo   Academic Record, Result and Attendance Management System (jamia_sms)
echo   Capstone Project-II (BTCSE 701) - Dec 18 Viva Ready
echo =====================================================================
echo.
echo Starting all 3 microservices in separate windows...
echo.

:: 1. Launch FastAPI Backend
echo [1/3] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "Jamia SMS - 1. FastAPI Backend (Port 8000)" cmd /k "title Jamia SMS - FastAPI Backend && cd /d "%PROJECT_DIR%" && color 0B && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: Safe 3-second delay
ping 127.0.0.1 -n 3 >nul

:: 2. Launch Streamlit Frontend
echo [2/3] Launching Streamlit Web Portal on http://localhost:8501 ...
start "Jamia SMS - 2. Streamlit Web Portal (Port 8501)" cmd /k "title Jamia SMS - Streamlit Portal && cd /d "%PROJECT_DIR%" && color 0E && python -m streamlit run app.py --server.port 8501"

:: Safe 3-second delay
ping 127.0.0.1 -n 3 >nul

:: 3. Launch ngrok Reverse Tunnel
echo [3/3] Launching ngrok Public Webhook Tunnel ...
where ngrok >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "Jamia SMS - 3. ngrok Webhook Tunnel" cmd /k "title Jamia SMS - ngrok Tunnel && color 0D && ngrok http 8000 --url=unstuck-cosigner-roving.ngrok-free.dev"
) else (
    start "Jamia SMS - 3. ngrok Webhook Tunnel" cmd /k "title Jamia SMS - ngrok Tunnel && color 0D && "%LOCALAPPDATA%\Microsoft\WinGet\Links\ngrok.exe" http 8000 --url=unstuck-cosigner-roving.ngrok-free.dev"
)

:: Safe 2-second delay then pop open browser
ping 127.0.0.1 -n 2 >nul
start http://localhost:8501

echo.
echo =====================================================================
echo   ALL 3 SERVICES LAUNCHED SUCCESSFULLY!
echo.
echo   - Backend Swagger Docs : http://localhost:8000/docs
echo   - Streamlit Dashboard  : http://localhost:8501 (Opened in browser)
echo   - Public ngrok URL     : https://unstuck-cosigner-roving.ngrok-free.dev
echo   - WhatsApp Webhook     : https://unstuck-cosigner-roving.ngrok-free.dev/webhook/whatsapp
echo.
echo   To STOP all services, run stop_jamia_sms.bat or press Ctrl+C in each window.
echo =====================================================================
echo.
pause
