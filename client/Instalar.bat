@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
  py -3.13 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto :error
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo Instalacion completa. Ejecuta Iniciar.bat para abrir el cliente.
pause
exit /b 0
:error
echo No se pudo instalar. Revisa Python y la conexion a Internet.
pause
exit /b 1
