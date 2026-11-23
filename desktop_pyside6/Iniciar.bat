@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" goto :not_installed

".venv\Scripts\python.exe" -c "import cv2, PySide6; assert hasattr(cv2, 'FaceDetectorYN')" >nul 2>&1
if errorlevel 1 goto :not_installed

".venv\Scripts\python.exe" desktop.py %*
if errorlevel 1 goto :runtime_error
exit /b 0

:not_installed
echo La aplicacion todavia no esta instalada.
echo Ejecuta Instalar.bat una vez y despues usa Iniciar.bat.
pause
exit /b 1

:runtime_error
echo.
echo La aplicacion se cerro con un error. Revisa el mensaje anterior.
pause
exit /b 1
