@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

echo ========================================
echo   Instalador VigiWork - Servidor
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creando el entorno virtual con Python 3.13...
    py -3.13 -m venv .venv
    if errorlevel 1 py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 goto :python_error
)

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_error

if not exist "tools" mkdir "tools"
if not exist "tools\cloudflared.exe" (
    echo Descargando Cloudflare Tunnel para acceso remoto...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'tools\cloudflared.exe'"
    if errorlevel 1 goto :cloudflared_error
)

echo Comprobando OpenCV y PySide6...
".venv\Scripts\python.exe" -c "import cv2, PySide6; assert hasattr(cv2, 'dnn') and hasattr(cv2.dnn, 'readNetFromONNX')"
if errorlevel 1 goto :install_error

echo Descargando y preparando el detector de cascos...
".venv\Scripts\python.exe" -c "from helmet_detector import load_detector; detector = load_detector(); print('Backend disponible:', detector.backend)"
if errorlevel 1 goto :model_error

echo.
echo Instalacion completa. Ya podes abrir Iniciar.bat.
pause
exit /b 0

:python_error
echo.
echo No se encontro Python 3. Instalalo desde https://www.python.org/downloads/ y volve a ejecutar este archivo.
pause
exit /b 1

:install_error
echo.
echo No se pudieron instalar las dependencias. Revisa la conexion a Internet y el error anterior.
pause
exit /b 1

:model_error
echo.
echo No se pudo descargar o preparar el modelo de cascos. Revisa la conexion a Internet y volve a ejecutar Instalar.bat.
pause
exit /b 1

:cloudflared_error
echo.
echo No se pudo descargar cloudflared. Revisa la conexion a Internet y vuelve a ejecutar Instalar.bat.
pause
exit /b 1
