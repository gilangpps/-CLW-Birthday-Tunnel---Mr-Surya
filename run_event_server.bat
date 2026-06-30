@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install -r server\requirements.txt

echo.
echo Birthday installation server
echo Visitor form: http://localhost:8080/
echo QR tablet:    http://localhost:8080/qr
echo Admin:        http://localhost:8080/admin
echo.
echo For visitor phones, replace localhost with this computer's local IP.
echo Press Ctrl+C to stop.
echo.

waitress-serve --host=0.0.0.0 --port=8080 "server.app:app"
