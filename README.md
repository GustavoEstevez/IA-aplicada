# VigiWork

Sistema de supervisión de cámaras de seguridad con detección local de casco y un cliente de visualización.

## Estructura

```text
server/       Captura RTSP, detector de cascos y servidor MJPEG
client/       Cliente de escritorio que recibe y muestra el video
shared/       Estilos, colores y recursos de marca compartidos
```

El servidor es el único que almacena URLs RTSP y administra cámaras. El cliente recibe el video por la red local y no puede agregar cámaras.

## Puesta en marcha

Los instaladores gráficos `.exe` para Windows 10/11 se compilan con Inno Setup desde `instaladores/Compilar-Instaladores.bat`. Genera los instaladores de servidor y cliente en `instaladores/salida/`; ambos incluyen el programa, instalan sus dependencias y permiten crear un acceso directo en el escritorio.

1. Ejecutá `server/Instalar.bat` y después `server/Iniciar.bat` en la computadora conectada a las cámaras.
2. Ejecutá `client/Instalar.bat` y `client/Iniciar.bat` en la computadora donde vas a mirar el video.
3. Para conectarte desde la misma red, ingresá la dirección local del servidor. Para conectarte desde cualquier lugar, en el servidor tocá **Crear enlace Cloudflare** y copiá la URL y la clave de acceso en la ventana **Configurar servidor** del cliente. El cliente guarda ambos datos y vuelve a conectarse automáticamente en los próximos inicios.

El enlace de Cloudflare es temporal: funciona mientras el servidor y el túnel estén abiertos, y puede cambiar al volver a crearlo. Si cambia, actualizá la dirección en el cliente. El acceso requiere la clave generada por el servidor.

Las cámaras, sus credenciales y las preferencias de IA se guardan en `server/cameras.json`. El modelo ONNX necesario se descarga en `server/models/` durante la instalación. Esos archivos son datos de trabajo del servidor, no copias descartables.

La interfaz usa los colores de marca negro `#1F1F1F`, naranja `#FF7A00` y blanco `#F2F2F2`, compartidos desde `shared/theme.py`.
