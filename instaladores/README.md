# Instaladores para Windows 10 y 11

Los instaladores gráficos `.exe` se compilan con Inno Setup. Ejecutá `Compilar-Instaladores.bat`; genera `salida/VigiWork-Servidor-Setup.exe` y `salida/VigiWork-Cliente-Setup.exe`. Cada uno muestra el asistente de instalación en español, instala la app en el perfil del usuario y ofrece crear el acceso directo del escritorio.

En cada computadora, ejecutá el `.exe` correspondiente y avanzá con **Siguiente**. Durante la instalación, el asistente prepara Python 3.13 para el usuario si hace falta e instala las dependencias. El instalador del servidor también descarga el modelo de cascos y Cloudflare Tunnel. Si la preparación falla, el asistente indica la ruta del registro detallado en `%LOCALAPPDATA%\VigiWork\Logs`.

Para volver a compilar, se necesita Inno Setup 6 y el código fuente del proyecto. Los `.exe` generados contienen la app y sus archivos; necesitan Internet durante la instalación para descargar Python, dependencias y, en servidor, el modelo y Cloudflare Tunnel. Los datos de cámaras y la clave permanecen locales en el equipo servidor.
