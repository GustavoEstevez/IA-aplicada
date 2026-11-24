# VigiWork · Cliente

Cliente PySide6 para ver el flujo MJPEG procesado por la app servidor. No necesita conocer ni guardar la URL RTSP ni las credenciales de la cámara.

## Inicio

1. En la computadora que tiene la cámara, iniciá el servidor desde `server\Iniciar.bat` y tocá **Probar**. Para acceso remoto, tocá **Crear enlace Cloudflare** en la ventana principal del servidor y copiá su URL y clave.
2. En esta computadora, ejecutá `Instalar.bat` una vez y luego `Iniciar.bat`.
3. En la ventana **Configurar servidor** del cliente, escribí la dirección local (`http://192.168.1.20:8765`) o la URL `https://….trycloudflare.com`, ingresá la clave del servidor y tocá **Conectar**.
4. El selector **Cámaras** muestra las que guardaste en el servidor. Elegí una y tocá **Usar cámara** para pedirle que cambie el video. **Actualizar cámaras** vuelve a cargar la lista. El cliente no puede agregar ni quitar cámaras.

El cliente muestra el video anotado con cascos y FPS, e intenta reconectarse si la señal se corta. La URL y clave se guardan localmente para futuras aperturas. Con Cloudflare, las computadoras pueden estar en redes distintas; el túnel debe permanecer abierto y su URL temporal puede cambiar. Los nombres de cámaras se consultan al servidor; las URLs RTSP y credenciales permanecen allí.

La conexión y la vista de video son ventanas independientes. La primera vez se abre la ventana **Configurar servidor**; al conectar aparece la vista normal en otra ventana. La dirección queda guardada y en las próximas aperturas el cliente muestra directamente la vista e intenta conectarse automáticamente. **Desconectar del servidor** corta el video, cierra la vista principal y vuelve a abrir la ventana de configuración con la dirección guardada.

El cliente autentica todas las solicitudes con la clave generada en el servidor. Protegé esa clave como una contraseña: cualquier persona que la tenga y conozca la URL puede ver el flujo y seleccionar cámaras.

## Instalación manual

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```
