@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" goto :not_installed
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 goto :not_installed
".venv\Scripts\python.exe" app.py %*
if errorlevel 1 goto :runtime_error
exit /b 0
:not_installed
echo Ejecuta Instalar.bat primero.
pause
exit /b 1
:runtime_error
echo La aplicacion se cerro con un error. Revisa el mensaje anterior.
pause
exit /b 1
