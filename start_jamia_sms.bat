@echo off
TITLE Jamia SMS - One-Click Launcher
COLOR 0A

:: 1. Navigate to the folder containing this batch file
cd /d "%~dp0"

:: 2. Detect Python executable
set "PY=C:\Users\atiff\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PY%" set "PY=python"

:: 3. Detect ngrok executable
set "NGROK=C:\Users\atiff\AppData\Local\Microsoft\WinGet\Links\ngrok.exe"
if not exist "%NGROK%" set "NGROK=ngrok"

echo =====================================================================
echo   JAMIA HAMDARD - SEST - DEPARTMENT OF COMPUTER SCIENCE AND ENG.
echo   Academic Record, Result and Attendance Management System (jamia_sms)
echo   Capstone Project-II (BTCSE 701) - Dec 18 Viva Ready
echo =====================================================================
echo.
echo Starting all 3 microservices in separate windows...
echo.

:: 1. Launch FastAPI Backend on Port 8000
echo [1/3] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "Jamia SMS - 1. FastAPI Backend (Port 8000)" cmd /k "color 0B && "%PY%" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: Wait 3 seconds
ping 127.0.0.1 -n 4 >nul

:: 2. Launch Streamlit Frontend on Port 8501
echo [2/3] Launching Streamlit Web Portal on http://localhost:8501 ...
start "Jamia SMS - 2. Streamlit Web Portal (Port 8501)" cmd /k "color 0E && "%PY%" -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false"

:: Wait 3 seconds
ping 127.0.0.1 -n 4 >nul

:: 3. Launch ngrok Reverse Tunnel
echo [3/3] Launching ngrok Public Webhook Tunnel ...
start "Jamia SMS - 3. ngrok Webhook Tunnel" cmd /k "color 0D && "%NGROK%" http 8000 --url=unstuck-cosigner-roving.ngrok-free.dev"

:: Wait 5 seconds for Streamlit server to be 100% ready, then pop open browser
echo.
echo [!] Waiting for Streamlit server to bind port 8501...
ping 127.0.0.1 -n 6 >nul
echo [!] Opening Jamia Hamdard Portal in your browser...
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
