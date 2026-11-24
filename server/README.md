# VigiWork · Servidor

Aplicación de escritorio con PySide6. Abre cámaras RTSP con OpenCV/FFmpeg, detecta cascos de seguridad de obra y dibuja cajas. Si la cámara pierde la señal, reintenta automáticamente con pausas crecientes. La inferencia usa el módulo DNN de OpenCV y un modelo ONNX local; no requiere PyTorch, Ultralytics, Rust ni Cargo. La ventana principal administra el sistema; **Probar** abre una vista temporal y el cliente recibe el video para su uso normal.

Esta aplicación funciona como **servidor**. Tocá **Probar** para abrir la ventana de prueba, elegir una cámara e iniciar el servicio. Para la misma red, el cliente puede usar la dirección local. Para acceso remoto, tocá **Crear enlace Cloudflare** y compartí la URL temporal y la clave de acceso con el cliente. La URL solo funciona mientras la aplicación y el túnel estén activos, y cambia al crear un túnel nuevo. El cliente muestra el video procesado y los FPS recibidos. Solo el servidor puede agregar o quitar cámaras, y sus URLs y credenciales no se envían al cliente. No compartas la clave con personas que no deban ver el video.

## Inicio en Windows

1. Ejecutá **Instalar.bat** una vez. Crea `.venv`, instala las dependencias, descarga `cloudflared.exe` y prepara el detector ONNX en `models/helmet_detection.onnx`.
2. Para usar el programa, ejecutá **Iniciar.bat**.

Necesitás Python 3 instalado y conexión a Internet durante la instalación.

El enlace usa Cloudflare Quick Tunnels, no requiere cuenta ni dominio, y es temporal. Su URL pública puede cambiar cada vez que se inicia un túnel. Cloudflare documenta esta opción como apta para pruebas y desarrollo: [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

También se puede iniciar desde una terminal:

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Al iniciar, la ventana muestra la lista de cámaras guardadas sin abrir video. Tocá **Agregar cámara** para ingresar su nombre y URL RTSP; cada cámara tiene su propia casilla **IA**. Al agregar, quitar o cambiar la IA aparece un borrador: **Aplicar cambios** lo guarda y reinicia el servicio, y **Cancelar** lo descarta. **Probar** abre una ventana separada para elegir una cámara y ver su stream; el servidor también envía ese video al cliente. Cerrar la ventana de prueba no interrumpe la transmisión al cliente. La configuración aplicada queda en `cameras.json`. Si la URL contiene credenciales, se guarda localmente en texto plano, así que no compartas ese archivo.

## GPU y detección

El detector marca los cascos de seguridad en verde y las detecciones `NO-Hardhat` en rojo. Intenta usar CUDA cuando OpenCV y el controlador NVIDIA lo permiten; después intenta OpenCL. Si la GPU no está disponible o falla, cambia a CPU automáticamente. La ventana muestra el backend activo, los FPS y ambos conteos.

El modelo base es YOLOv8n, afinado para EPP de construcción. OpenCV corre la inferencia desde ONNX sin instalar PyTorch. La clase `NO-Hardhat` puede fallar más que la clase de casco; el tamaño, la distancia, las oclusiones y la iluminación también afectan lo que detecta. El modelo no publica métricas de validación propias, así que revisá los resultados con las cámaras del lugar antes de usarlo como apoyo operativo.

Modelo: [Construction Site PPE Detector](https://huggingface.co/mancalazure/construction-ppe-safety), clases `Hardhat` y `NO-Hardhat`, licencia CC BY 4.0. La descarga está fijada a una revisión y se verifica con SHA-256. Los cuadros se procesan localmente y no se guardan.
