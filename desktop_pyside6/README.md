# RTSP Scout Escritorio

Aplicación de escritorio con PySide6. Python maneja la interfaz, abre la cámara RTSP con OpenCV/FFmpeg, detecta rostros, dibuja las cajas y calcula los FPS. No requiere Rust ni Cargo.

## Inicio en Windows

1. Ejecutá **Instalar.bat** una vez. Crea `.venv`, instala las dependencias y descarga el modelo YuNet a `models/`.
2. Para usar el programa, ejecutá **Iniciar.bat**.

Necesitás Python 3 instalado y conexión a Internet durante la instalación.

También se puede iniciar desde una terminal:

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python desktop.py
```

Pegá la URL completa de la cámara, por ejemplo `rtsp://usuario:contraseña@192.168.1.154:554/ruta`.

## GPU y detección

El detector intenta usar CUDA cuando OpenCV y el controlador NVIDIA lo permiten; después intenta OpenCL para GPUs compatibles de NVIDIA, AMD o Intel. Si esa computadora no tiene una GPU compatible, cambia a CPU automáticamente. El estado de la ventana muestra el backend activo. La aceleración por GPU depende de la GPU, los controladores y de que la compilación de OpenCV tenga ese backend; ningún programa puede garantizar usar la GPU en todas las computadoras antiguas.

El sistema **detecta y marca rostros**, pero no identifica nombres ni compara identidades. No guarda fotos o videos. El modelo [YuNet del OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) detecta rostros visibles; perfiles extremos, caras muy pequeñas, oclusiones y poca luz pueden reducir la precisión.
