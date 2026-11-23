#!/usr/bin/env python3
"""Visor RTSP de escritorio: captura y detección de rostros en Python."""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import cv2
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QVBoxLayout, QWidget,
)

from face_detector import draw_faces, load_detector


def masked_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.password is None:
        return value
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    netloc = f"{parts.username or ''}:•••@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class StreamWorker(QObject):
    frame = Signal(QImage)
    status = Signal(str, str)
    finished = Signal()

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._stop = threading.Event()
        self.capture = None

    def stop(self) -> None:
        self._stop.set()
        if self.capture is not None:
            self.capture.release()

    def _open_camera(self):
        option_name = "OPENCV_FFMPEG_CAPTURE_OPTIONS"
        previous = os.environ.get(option_name)
        os.environ[option_name] = "rtsp_transport;tcp"
        try:
            params = [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5_000,
            ]
            try:
                capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG, params)
            except (TypeError, cv2.error):
                capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        finally:
            if previous is None:
                os.environ.pop(option_name, None)
            else:
                os.environ[option_name] = previous
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("OpenCV/FFmpeg no pudo abrir la cámara. Revisá URL y credenciales.")
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def run(self) -> None:
        try:
            self.status.emit("Cargando detector de rostros…", "working")
            detector = load_detector()
            if self._stop.is_set():
                return
            self.status.emit("Conectando a la cámara RTSP con Python…", "working")
            self.capture = self._open_camera()
            backend = detector.backend
            self.status.emit(f"En vivo · IA {backend}", "live")
            last_status_at = 0.0
            while not self._stop.is_set():
                ok, frame = self.capture.read()
                if not ok or frame is None:
                    raise RuntimeError("La cámara dejó de enviar video.")
                faces = detector.detect(frame)
                count = draw_faces(frame, faces)
                if detector.backend != backend:
                    backend = detector.backend
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888).copy()
                self.frame.emit(image)
                now = time.monotonic()
                if now - last_status_at >= 1.0:
                    self.status.emit(f"En vivo · IA {backend} · {count} rostro(s)", "live")
                    last_status_at = now
        except Exception as exc:
            if not self._stop.is_set():
                self.status.emit(f"No se pudo iniciar: {exc}", "error")
        finally:
            if self.capture is not None:
                self.capture.release()
                self.capture = None
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RTSP Scout · Rostros")
        self.resize(1100, 700)
        self.thread: QThread | None = None
        self.worker: StreamWorker | None = None
        self.fps_count = 0
        self.fps_started_at = 0.0
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        brand = QLabel("CiberBoom")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(QLabel("Detección local de rostros"))
        layout.addLayout(header)

        layout.addWidget(QLabel("URL de la cámara"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("rtsp://usuario:contraseña@192.168.1.154:554/ruta")
        self.url.setClearButtonEnabled(True)
        layout.addWidget(self.url)
        layout.addWidget(QLabel("Incluí usuario, contraseña, IP, puerto y ruta en la URL."))

        actions = QHBoxLayout()
        self.connect_button = QPushButton("Conectar")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self.connect_camera)
        actions.addWidget(self.connect_button)
        self.disconnect_button = QPushButton("Desconectar")
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.disconnect_camera)
        actions.addWidget(self.disconnect_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.status = QLabel("Pegá la URL RTSP para detectar rostros")
        self.status.setObjectName("status")
        layout.addWidget(self.status)
        self.fps_label = QLabel("0 FPS IA")
        self.fps_label.setObjectName("fps")
        layout.addWidget(self.fps_label)
        self.video = QLabel("El video y la detección se procesan en esta computadora")
        self.video.setObjectName("video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(640, 360)
        layout.addWidget(self.video, 1)
        self.url_label = QLabel("—")
        self.url_label.setObjectName("url")
        layout.addWidget(self.url_label)
        self.setCentralWidget(root)
        self.setStyleSheet("""
            QWidget#root { background:#0b1026; color:#e8ebf5; font:14px 'Segoe UI'; }
            QLabel#brand { color:#fff; font-size:23px; font-weight:700; }
            QLineEdit { background:#151c38; border:1px solid #333d60; border-radius:8px; padding:12px; color:#fff; }
            QPushButton { background:#202947; border:0; border-radius:8px; padding:11px 18px; color:#fff; }
            QPushButton#primary { background:#5372ed; font-weight:600; }
            QPushButton:disabled { color:#8991aa; background:#252b40; }
            QLabel#status { color:#aeb8dc; }
            QLabel#fps { color:#80d7a4; font-weight:600; }
            QLabel#video { background:#050711; border:1px solid #242a42; border-radius:12px; color:#79819a; }
            QLabel#url { color:#8991aa; }
        """)

    def connect_camera(self) -> None:
        url = self.url.text().strip()
        if not re.match(r"^rtsps?://", url, re.I):
            self.status.setText("La URL debe empezar con rtsp:// o rtsps://.")
            return
        if not self.disconnect_camera():
            return
        self.url_label.setText(masked_url(url))
        self.status.setText("Preparando la cámara y la IA…")
        self.video.setText("Conectando…")
        self.fps_count = 0
        self.fps_started_at = time.monotonic()
        self.fps_label.setText("0 FPS IA")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        thread = QThread(self)
        worker = StreamWorker(url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.frame.connect(self.show_frame)
        worker.status.connect(self.show_status)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_finished)
        self.thread, self.worker = thread, worker
        thread.start()

    def show_frame(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video.setPixmap(pixmap)
        self.fps_count += 1
        elapsed = time.monotonic() - self.fps_started_at
        if elapsed >= 1:
            self.fps_label.setText(f"{self.fps_count / elapsed:.1f} FPS IA")
            self.fps_count = 0
            self.fps_started_at = time.monotonic()

    def show_status(self, message: str, kind: str) -> None:
        self.status.setText(message)
        color = "#f08d8d" if kind == "error" else ("#80d7a4" if kind == "live" else "#aeb8dc")
        self.status.setStyleSheet(f"color:{color}")

    def _thread_finished(self) -> None:
        self.thread = None
        self.worker = None
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

    def disconnect_camera(self) -> bool:
        worker, thread = self.worker, self.thread
        if worker and thread and thread.isRunning():
            worker.stop()
            thread.quit()
            thread.wait(2500)
            if thread.isRunning():
                self.status.setText("Esperando que termine la lectura del video…")
                return False
        self.worker = None
        self.thread = None
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.video.clear()
        self.video.setText("Pegá la URL RTSP para detectar rostros")
        self.fps_label.setText("0 FPS IA")
        self.status.setText("Esperando URL")
        self.status.setStyleSheet("")
        self.url_label.setText("—")
        return True

    def closeEvent(self, event) -> None:
        if self.disconnect_camera():
            event.accept()
        else:
            event.ignore()


def main() -> None:
    cv2.setNumThreads(max(1, min(4, cv2.getNumberOfCPUs())))
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
