@echo off
TITLE Jamia SMS - Shutdown Utility
COLOR 0C

echo =====================================================================
echo   JAMIA HAMDARD - STOPPING ALL JAMIA SMS SERVICES
echo =====================================================================
echo.

echo Stopping uvicorn / FastAPI processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Jamia SMS*" 2>nul
taskkill /F /IM ngrok.exe 2>nul

echo.
echo All Jamia SMS background processes stopped.
echo =====================================================================
timeout /t 3 >nul
