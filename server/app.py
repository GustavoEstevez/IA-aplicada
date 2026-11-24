#!/usr/bin/env python3
"""Visor RTSP de escritorio con detección local de cascos de seguridad."""
from __future__ import annotations

import os
import json
import re
import socket
import sys
import threading
import time
import secrets
import shutil
import subprocess
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QVBoxLayout, QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.theme import APP_STYLESHEET, app_icon, brand_header, scrollable
from helmet_detector import draw_helmets, load_detector
from video_server import VideoHub

CAMERAS_FILE = Path(__file__).resolve().parent / "cameras.json"
ACCESS_KEY_FILE = Path(__file__).resolve().parent / "access_key.txt"
CLOUDFLARED_FILE = Path(__file__).resolve().parent / "tools" / "cloudflared.exe"
CLOUDFLARE_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)


def load_access_key() -> str:
    try:
        key = ACCESS_KEY_FILE.read_text(encoding="utf-8").strip()
        if len(key) >= 40:
            return key
    except OSError:
        pass
    key = secrets.token_urlsafe(48)
    temporary = ACCESS_KEY_FILE.with_suffix(".txt.tmp")
    temporary.write_text(key, encoding="utf-8")
    os.replace(temporary, ACCESS_KEY_FILE)
    return key


class CloudflareTunnelWorker(QObject):
    url_ready = Signal(str)
    status = Signal(str)
    finished = Signal(str)

    def __init__(self, executable: str):
        super().__init__()
        self.executable = executable
        self.stopping = threading.Event()
        self.process: subprocess.Popen | None = None

    def stop(self) -> None:
        self.stopping.set()
        process = self.process
        if process and process.poll() is None:
            process.terminate()

    def run(self) -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                [self.executable, "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8765"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
            self.status.emit("Conectando con Cloudflare…")
            found_url = ""
            assert self.process.stdout is not None
            for line in self.process.stdout:
                match = CLOUDFLARE_URL_RE.search(line)
                if match:
                    found_url = match.group(0)
                    self.url_ready.emit(found_url)
                    self.status.emit("Enlace de Cloudflare activo")
            code = self.process.wait()
            if not self.stopping.is_set():
                self.finished.emit(f"cloudflared terminó (código {code}).")
            else:
                self.finished.emit("")
        except OSError as exc:
            self.finished.emit(f"No se pudo ejecutar cloudflared: {exc}")
        except Exception as exc:
            self.finished.emit(f"Falló el túnel de Cloudflare: {exc}")


class AddCameraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar cámara")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(APP_STYLESHEET)
        root = QVBoxLayout(self)
        root.addWidget(brand_header("Agregar cámara", "Guardá una cámara RTSP en el servidor"))
        form = QFormLayout()
        root.addLayout(form)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ej. Entrada principal")
        self.url = QLineEdit()
        self.url.setPlaceholderText("rtsp://usuario:contraseña@192.168.1.154:554/ruta")
        form.addRow("Nombre", self.name)
        form.addRow("URL RTSP", self.url)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def camera(self) -> dict[str, str]:
        return {
            "name": self.name.text().strip(),
            "url": self.url.text().strip(),
        }


class CameraPreviewDialog(QDialog):
    camera_selected = Signal(str)

    def __init__(self, cameras: list[dict[str, object]], selected_url: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("VigiWork · Prueba de cámaras")
        self.setWindowIcon(app_icon())
        self.resize(960, 650)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(brand_header("Prueba de cámara", "Diagnóstico de señal en vivo"))
        layout.addWidget(QLabel("Cámara para probar"))
        self.selector = QComboBox()
        for camera in cameras:
            self.selector.addItem(str(camera["name"]), str(camera["url"]))
        layout.addWidget(self.selector)
        self.status = QLabel("Esperando video de la cámara…")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.video = QLabel("Conectando con la cámara…")
        self.video.setObjectName("preview")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(320, 240)
        layout.addWidget(self.video, 1)
        self.setStyleSheet(APP_STYLESHEET)
        self.selector.currentIndexChanged.connect(self._selection_changed)
        index = self.selector.findData(selected_url) if selected_url else -1
        self.selector.setCurrentIndex(index if index >= 0 else 0)

    def _selection_changed(self, _index: int) -> None:
        url = self.selector.currentData()
        if url:
            self.video.clear()
            self.video.setText("Conectando con la cámara…")
            self.camera_selected.emit(str(url))

    def show_frame(self, image: QImage) -> None:
        self.video.setPixmap(QPixmap.fromImage(image).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def show_status(self, message: str, _kind: str) -> None:
        self.status.setText(message)


class StreamWorker(QObject):
    frame = Signal(QImage)
    status = Signal(str, str)
    finished = Signal()

    def __init__(self, url: str, video_hub: VideoHub, ai_enabled: bool = True, preview_enabled: bool = False):
        super().__init__()
        self.url = url
        self.video_hub = video_hub
        self.ai_enabled = ai_enabled
        self.preview_enabled = preview_enabled
        self._stop = threading.Event()
        self.capture = None

    def stop(self) -> None:
        self._stop.set()
        if self.capture is not None:
            self.capture.release()

    def _release_capture(self) -> None:
        capture, self.capture = self.capture, None
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

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
            detector = None
            if self.ai_enabled:
                self.status.emit("Cargando detector de cascos…", "working")
                detector = load_detector()
            if self._stop.is_set():
                return
            backend = detector.backend if detector is not None else "IA apagada"
            retry_delay = 1
            while not self._stop.is_set():
                connected_at = None
                try:
                    self.status.emit("Conectando a la cámara RTSP…", "working")
                    self.capture = self._open_camera()
                    connected_at = time.monotonic()
                    self.status.emit(f"En vivo · {backend}", "live")
                    last_status_at = 0.0
                    while not self._stop.is_set():
                        ok, frame = self.capture.read()
                        if not ok or frame is None:
                            raise RuntimeError("La cámara dejó de enviar video.")
                        if detector is not None:
                            helmets = detector.detect(frame)
                            helmet_count, no_helmet_count = draw_helmets(frame, helmets)
                            if detector.backend != backend:
                                backend = detector.backend
                        else:
                            helmet_count = no_helmet_count = 0
                        if self.preview_enabled:
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            height, width = rgb.shape[:2]
                            image = QImage(
                                rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888
                            ).copy()
                            self.frame.emit(image)
                        if self.video_hub.running:
                            encoded, buffer = cv2.imencode(
                                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                            )
                            if encoded:
                                self.video_hub.publish(buffer.tobytes())
                        now = time.monotonic()
                        if now - last_status_at >= 1.0:
                            if detector is None:
                                message = "En vivo · IA apagada"
                            else:
                                message = (
                                    f"En vivo · Detector {backend} · Cascos: {helmet_count} "
                                    f"· Sin casco: {no_helmet_count}"
                                )
                            self.status.emit(message, "live")
                            last_status_at = now
                except Exception as exc:
                    if self._stop.is_set():
                        break
                    self._release_capture()
                    self.video_hub.clear()
                    self.status.emit(
                        f"Se interrumpió la señal RTSP. Reintentando en {retry_delay}s…",
                        "working",
                    )
                    self._stop.wait(retry_delay)
                    if connected_at is not None and time.monotonic() - connected_at >= 10:
                        retry_delay = 1
                    else:
                        retry_delay = min(retry_delay * 2, 10)
                else:
                    break
                finally:
                    if self._stop.is_set():
                        self._release_capture()
        except Exception as exc:
            if not self._stop.is_set():
                self.status.emit(f"No se pudo iniciar: {exc}", "error")
        finally:
            self._release_capture()
            self.video_hub.clear()
            self.finished.emit()


class MainWindow(QMainWindow):
    remote_camera_requested = Signal(str, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VigiWork · Servidor")
        self.setWindowIcon(app_icon())
        self.resize(1100, 700)
        self.thread: QThread | None = None
        self.worker: StreamWorker | None = None
        self.preview_window: CameraPreviewDialog | None = None
        self._cameras: list[dict[str, object]] = []
        self._applied_cameras: list[dict[str, object]] = []
        self._has_pending_changes = False
        self.access_key = load_access_key()
        self.video_hub = VideoHub()
        self.video_hub.set_access_key(self.access_key)
        self.tunnel_thread: QThread | None = None
        self.tunnel_worker: CloudflareTunnelWorker | None = None
        self.public_url = ""
        self.video_hub.select_callback = self.remote_camera_requested.emit
        self.remote_camera_requested.connect(self._connect_remote_camera)
        self._build_ui()
        self._load_cameras()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        layout.addWidget(brand_header("Servidor de cámaras", "Detección de cascos y transmisión al cliente"))

        cameras_heading = QLabel("Cámaras guardadas · activar IA por cámara")
        cameras_heading.setObjectName("eyebrow")
        layout.addWidget(cameras_heading)
        self.camera_list = QTreeWidget()
        self.camera_list.setColumnCount(2)
        self.camera_list.setHeaderLabels(["Cámara", "IA"])
        self.camera_list.setRootIsDecorated(False)
        self.camera_list.setAlternatingRowColors(True)
        self.camera_list.setMinimumHeight(145)
        self.camera_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.camera_list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.camera_list.itemSelectionChanged.connect(self._selection_changed)
        self.camera_list.itemChanged.connect(self._camera_item_changed)
        layout.addWidget(self.camera_list)
        camera_row = QHBoxLayout()
        self.save_camera_button = QPushButton("Agregar cámara")
        self.save_camera_button.clicked.connect(self.save_camera)
        camera_row.addWidget(self.save_camera_button)
        self.remove_camera_button = QPushButton("Quitar")
        self.remove_camera_button.setObjectName("danger")
        self.remove_camera_button.clicked.connect(self.remove_camera)
        camera_row.addWidget(self.remove_camera_button)
        layout.addLayout(camera_row)

        changes_row = QHBoxLayout()
        self.apply_changes_button = QPushButton("Aplicar cambios")
        self.apply_changes_button.setObjectName("primary")
        self.apply_changes_button.setEnabled(False)
        self.apply_changes_button.clicked.connect(self.apply_changes)
        changes_row.addWidget(self.apply_changes_button)
        self.cancel_changes_button = QPushButton("Cancelar")
        self.cancel_changes_button.setEnabled(False)
        self.cancel_changes_button.clicked.connect(self.cancel_changes)
        changes_row.addWidget(self.cancel_changes_button)
        changes_row.addStretch()
        layout.addLayout(changes_row)
        self.pending_label = QLabel("Sin cambios pendientes")
        self.pending_label.setObjectName("status")
        self.pending_label.setWordWrap(True)
        self.pending_label.hide()
        layout.addWidget(self.pending_label)

        self.test_button = QPushButton("Probar cámara")
        self.test_button.setObjectName("primary")
        self.test_button.clicked.connect(self.test_camera)
        layout.addWidget(self.test_button)

        server_row = QHBoxLayout()
        self.server_button = QPushButton("Iniciar servidor")
        self.server_button.clicked.connect(self.toggle_server)
        server_row.addWidget(self.server_button)
        self.server_address = QLabel("Servidor detenido")
        self.server_address.setObjectName("status")
        server_row.addWidget(self.server_address, 1)
        layout.addLayout(server_row)

        remote_access_panel = QWidget()
        remote_layout = QVBoxLayout(remote_access_panel)
        remote_layout.setContentsMargins(0, 0, 0, 0)
        remote_layout.setSpacing(10)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Contraseña del cliente"))
        self.access_key_input = QLineEdit(self.access_key)
        self.access_key_input.setReadOnly(True)
        self.access_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.access_key_input, 1)
        self.copy_key_button = QPushButton("Copiar contraseña")
        self.copy_key_button.clicked.connect(self.copy_access_key)
        key_row.addWidget(self.copy_key_button)
        remote_layout.addLayout(key_row)

        tunnel_row = QHBoxLayout()
        self.cloudflare_button = QPushButton("Crear enlace Cloudflare")
        self.cloudflare_button.clicked.connect(self.toggle_cloudflare)
        tunnel_row.addWidget(self.cloudflare_button)
        self.cloudflare_status = QLabel("Acceso remoto apagado")
        self.cloudflare_status.setObjectName("subtle")
        tunnel_row.addWidget(self.cloudflare_status, 1)
        remote_layout.addLayout(tunnel_row)

        url_row = QHBoxLayout()
        self.cloudflare_url_label = QLabel("—")
        self.cloudflare_url_label.setObjectName("url")
        self.cloudflare_url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        url_row.addWidget(QLabel("URL pública"))
        url_row.addWidget(self.cloudflare_url_label, 1)
        self.copy_url_button = QPushButton("Copiar URL")
        self.copy_url_button.setEnabled(False)
        self.copy_url_button.clicked.connect(self.copy_cloudflare_url)
        url_row.addWidget(self.copy_url_button)
        remote_layout.addLayout(url_row)
        remote_access_panel.setVisible(False)
        layout.addWidget(remote_access_panel)
        self.remote_access_panel = remote_access_panel

        self.status = QLabel("Agregá o seleccioná una cámara para comenzar")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.setCentralWidget(scrollable(root))
        self.setStyleSheet(APP_STYLESHEET)

    def connect_camera(self, camera: dict[str, object] | None = None) -> None:
        item = self.camera_list.currentItem()
        url = camera.get("url") if camera else (item.data(0, Qt.ItemDataRole.UserRole) if item else None)
        if not url:
            self._set_status("Seleccioná una cámara guardada o agregá una nueva.")
            return
        self.video_hub.set_cameras(self._applied_cameras if camera else self._cameras, str(url))
        if not self.disconnect_camera():
            return
        self._set_status("Preparando la cámara y el detector…")
        thread = QThread(self)
        ai_enabled = bool(camera.get("ai_enabled", True)) if camera else item.checkState(1) == Qt.CheckState.Checked
        preview_enabled = bool(self.preview_window and self.preview_window.isVisible())
        worker = StreamWorker(str(url), self.video_hub, ai_enabled, preview_enabled)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.show_status)
        if preview_enabled and self.preview_window:
            worker.frame.connect(self.preview_window.show_frame)
            worker.status.connect(self.preview_window.show_status)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_finished)
        self.thread, self.worker = thread, worker
        thread.start()
        if preview_enabled:
            self.test_button.setText("Cerrar prueba")

    def test_camera(self) -> None:
        if self.preview_window and self.preview_window.isVisible():
            self.preview_window.close()
            return
        if not self._applied_cameras:
            self._set_status("Agregá o seleccioná una cámara antes de probarla.")
            return
        if self._has_pending_changes:
            return
        current = self.camera_list.currentItem()
        selected_url = current.data(0, Qt.ItemDataRole.UserRole) if current else ""
        if not selected_url:
            selected_url = str(self._applied_cameras[0]["url"])
        self.preview_window = CameraPreviewDialog(self._applied_cameras, str(selected_url), self)
        self.preview_window.camera_selected.connect(self._preview_camera_selected)
        self.preview_window.finished.connect(self._camera_test_closed)
        self.preview_window.show()
        self.test_button.setText("Cerrar prueba")
        if not self.video_hub.running:
            self.toggle_server()
            if not self.video_hub.running:
                self.preview_window.close()
                return
        QTimer.singleShot(0, lambda: self._preview_camera_selected(str(selected_url)))

    def _preview_camera_selected(self, url: str) -> None:
        camera = next((item for item in self._applied_cameras if item["url"] == url), None)
        if camera is None:
            return
        for index in range(self.camera_list.topLevelItemCount()):
            item = self.camera_list.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole) == url:
                self.camera_list.setCurrentItem(item)
                break
        self.connect_camera(camera)

    def _camera_test_closed(self, _result: int = 0) -> None:
        if self.worker:
            self.worker.preview_enabled = False
        self.preview_window = None
        self.test_button.setText("Probar")

    def _update_pending_changes(self) -> None:
        self._has_pending_changes = self._cameras != self._applied_cameras
        self.apply_changes_button.setEnabled(self._has_pending_changes)
        self.cancel_changes_button.setEnabled(self._has_pending_changes)
        self.test_button.setEnabled(not self._has_pending_changes)
        if self._has_pending_changes:
            self.pending_label.setText("Hay cambios pendientes. Aplicalos para reiniciar el servicio o cancelalos para descartarlos.")
            self.pending_label.show()
        else:
            self.pending_label.hide()

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
        self.status.show()

    def cancel_changes(self) -> None:
        self._cameras = [dict(camera) for camera in self._applied_cameras]
        self._refresh_camera_list()
        self._update_pending_changes()
        self._set_status("Cambios descartados; se mantiene la configuración aplicada.")

    def apply_changes(self) -> None:
        if not self._has_pending_changes:
            return
        selected_item = self.camera_list.currentItem()
        selected_url = selected_item.data(0, Qt.ItemDataRole.UserRole) if selected_item else ""
        was_streaming = bool(self.thread and self.thread.isRunning())
        active_url = self.worker.url if was_streaming and self.worker else ""
        was_server_running = self.video_hub.running
        if was_streaming and not self.disconnect_camera():
            self._set_status("Esperando que termine la lectura del video antes de aplicar los cambios…")
            return
        try:
            self._save_camera_file()
        except OSError as exc:
            QMessageBox.critical(self, "No se pudo aplicar", f"No pude guardar cameras.json:\n{exc}")
            old_camera = next((camera for camera in self._applied_cameras if camera["url"] == active_url), None)
            if old_camera:
                self.connect_camera(old_camera)
            return

        self._applied_cameras = [dict(camera) for camera in self._cameras]
        service_restarted = False
        if was_server_running:
            self.video_hub.stop()
        self.video_hub.set_cameras(self._applied_cameras, str(selected_url or ""))
        if was_server_running:
            try:
                self.video_hub.start(port=8765)
            except OSError as exc:
                self.server_button.setText("Iniciar servidor")
                self.server_address.setText("Servidor detenido")
                self.remote_access_panel.hide()
                QMessageBox.critical(self, "No se pudo reiniciar el servidor", str(exc))
            else:
                service_restarted = True
                self.server_button.setText("Detener servidor")
                self.server_address.setText(f"Cliente: http://{self._local_ip()}:8765")
        selected_index = next(
            (index for index, camera in enumerate(self._cameras) if camera["url"] == selected_url),
            -1,
        )
        self._refresh_camera_list(selected_index)
        self._update_pending_changes()
        self._set_status(
            "Cambios aplicados y servicio reiniciado." if service_restarted
            else ("Cambios aplicados, pero el servicio no pudo reiniciarse." if was_server_running
                  else "Cambios aplicados. El servicio está detenido.")
        )
        if (was_streaming or self.preview_window is not None) and selected_url:
            selected_camera = next((camera for camera in self._applied_cameras if camera["url"] == selected_url), None)
            if selected_camera:
                self.connect_camera(selected_camera)

    def _selection_changed(self) -> None:
        self.remove_camera_button.setEnabled(self.camera_list.currentItem() is not None)

    def _camera_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 1:
            return
        index = self.camera_list.indexOfTopLevelItem(item)
        if 0 <= index < len(self._cameras):
            self._cameras[index]["ai_enabled"] = item.checkState(1) == Qt.CheckState.Checked
            self._update_pending_changes()

    def toggle_server(self) -> None:
        if self.video_hub.running:
            if self.tunnel_thread and self.tunnel_thread.isRunning():
                self.stop_cloudflare()
            self.video_hub.stop()
            self.server_button.setText("Iniciar servidor")
            self.server_address.setText("Servidor detenido")
            self.status.hide()
            self.remote_access_panel.hide()
            return
        try:
            self.video_hub.start(port=8765)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "No se pudo iniciar el servidor",
                f"No pude abrir el puerto 8765. Puede estar ocupado o bloqueado por el firewall.\n{exc}",
            )
            return
        address = self._local_ip()
        self.server_button.setText("Detener servidor")
        self.server_address.setText(f"Cliente: http://{address}:8765")
        self.remote_access_panel.show()
        self._set_status("Servidor listo; conectá una cámara para compartir el video.")

    def toggle_cloudflare(self) -> None:
        if self.tunnel_thread and self.tunnel_thread.isRunning():
            self.stop_cloudflare()
            return
        if not self.video_hub.running:
            return

        executable = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
        if not executable and CLOUDFLARED_FILE.is_file():
            executable = str(CLOUDFLARED_FILE)
        if not executable:
            QMessageBox.warning(
                self,
                "Falta cloudflared",
                "No encuentro cloudflared. Ejecutá server\\Instalar.bat para instalarlo y volvé a intentar.",
            )
            return

        self.public_url = ""
        self.cloudflare_url_label.setText("Generando enlace seguro…")
        self.copy_url_button.setEnabled(False)
        self.cloudflare_button.setText("Detener enlace Cloudflare")
        self.cloudflare_status.setText("Iniciando túnel…")
        thread = QThread(self)
        worker = CloudflareTunnelWorker(executable)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.url_ready.connect(self._cloudflare_url_ready)
        worker.status.connect(self.cloudflare_status.setText)
        worker.finished.connect(self._cloudflare_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cloudflare_thread_finished)
        self.tunnel_thread, self.tunnel_worker = thread, worker
        thread.start()

    def _cloudflare_url_ready(self, public_url: str) -> None:
        self.public_url = public_url
        self.cloudflare_url_label.setText(public_url)
        self.copy_url_button.setEnabled(True)

    def _cloudflare_finished(self, message: str) -> None:
        self.cloudflare_button.setText("Crear enlace Cloudflare")
        self.copy_url_button.setEnabled(False)
        if message:
            self.cloudflare_status.setText(message)
            self.cloudflare_url_label.setText("—")
            self.public_url = ""
        else:
            self.cloudflare_status.setText("Acceso remoto apagado")

    def _cloudflare_thread_finished(self) -> None:
        self.tunnel_thread = None
        self.tunnel_worker = None

    def stop_cloudflare(self) -> None:
        worker, thread = self.tunnel_worker, self.tunnel_thread
        if worker:
            worker.stop()
        if thread and thread.isRunning():
            thread.quit()
            thread.wait(3000)
        if thread and thread.isRunning():
            self.cloudflare_status.setText("Esperando que cierre cloudflared…")
            return
        self.tunnel_worker = None
        self.tunnel_thread = None
        self.cloudflare_button.setText("Crear enlace Cloudflare")
        self.cloudflare_status.setText("Acceso remoto apagado")
        self.cloudflare_url_label.setText("—")
        self.copy_url_button.setEnabled(False)
        self.public_url = ""

    def copy_cloudflare_url(self) -> None:
        if self.public_url:
            QApplication.clipboard().setText(self.public_url)

    def copy_access_key(self) -> None:
        QApplication.clipboard().setText(self.access_key)

    @staticmethod
    def _local_ip() -> str:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 80))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            probe.close()

    def _load_cameras(self) -> None:
        try:
            data = json.loads(CAMERAS_FILE.read_text(encoding="utf-8"))
            self._cameras = [
                {
                    "name": str(item["name"]).strip(),
                    "url": str(item["url"]).strip(),
                    "ai_enabled": bool(item.get("ai_enabled", True)),
                }
                for item in data
                if isinstance(item, dict)
                and item.get("name")
                and re.match(r"^rtsps?://", str(item.get("url", "")), re.I)
            ]
        except FileNotFoundError:
            self._cameras = []
        except (OSError, ValueError, TypeError, KeyError):
            self._cameras = []
            self._set_status("No se pudo leer cameras.json; podés volver a guardar las cámaras.")
        self._applied_cameras = [dict(camera) for camera in self._cameras]
        self._refresh_camera_list()
        selected_item = self.camera_list.currentItem()
        self.video_hub.set_cameras(
            self._applied_cameras,
            selected_item.data(0, Qt.ItemDataRole.UserRole) if selected_item else "",
        )
        self._update_pending_changes()

    def _save_camera_file(self) -> None:
        temporary = CAMERAS_FILE.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._cameras, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, CAMERAS_FILE)

    def _refresh_camera_list(self, selected: int = -1) -> None:
        self.camera_list.blockSignals(True)
        self.camera_list.clear()
        for camera in self._cameras:
            item = QTreeWidgetItem([camera["name"], ""])
            item.setData(0, Qt.ItemDataRole.UserRole, camera["url"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(1, Qt.CheckState.Checked if camera.get("ai_enabled", True) else Qt.CheckState.Unchecked)
            self.camera_list.addTopLevelItem(item)
        if 0 <= selected < len(self._cameras):
            self.camera_list.setCurrentItem(self.camera_list.topLevelItem(selected))
        self.camera_list.blockSignals(False)
        self._selection_changed()

    def _connect_remote_camera(self, url: str, _ai_enabled: bool) -> None:
        camera = next((entry for entry in self._applied_cameras if entry["url"] == url), None)
        if camera is None:
            return
        if self.preview_window and self.preview_window.isVisible():
            index = self.preview_window.selector.findData(url)
            if index >= 0:
                self.preview_window.selector.setCurrentIndex(index)
                return
        for index in range(self.camera_list.topLevelItemCount()):
            item = self.camera_list.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole) == url:
                self.camera_list.setCurrentItem(item)
                break
        self.connect_camera(camera)

    def save_camera(self) -> None:
        dialog = AddCameraDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        record = dialog.camera()
        if not record["name"] or not re.match(r"^rtsps?://", record["url"], re.I):
            QMessageBox.warning(
                self,
                "Faltan datos",
                "Completá el nombre y una URL que empiece con rtsp:// o rtsps://.",
            )
            return
        record["ai_enabled"] = True
        existing = next((i for i, item in enumerate(self._cameras) if item["url"] == record["url"]), None)
        if existing is None:
            self._cameras.append(record)
            selected = len(self._cameras) - 1
        else:
            record["ai_enabled"] = self._cameras[existing].get("ai_enabled", True)
            self._cameras[existing] = record
            selected = existing
        self._refresh_camera_list(selected)
        self._update_pending_changes()
        self._set_status(f"Cámara «{record['name']}» agregada al borrador; aplicá los cambios para usarla.")

    def remove_camera(self) -> None:
        index = self.camera_list.indexOfTopLevelItem(self.camera_list.currentItem())
        if not 0 <= index < len(self._cameras):
            return
        name = self._cameras[index]["name"]
        answer = QMessageBox.question(
            self, "Quitar cámara", f"¿Quitar «{name}» de la lista guardada?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self._cameras.pop(index)
        self._refresh_camera_list(min(index, len(self._cameras) - 1))
        self._update_pending_changes()
        self._set_status(f"Cámara «{name}» quitada del borrador; aplicá los cambios para confirmarlo.")

    def show_status(self, message: str, kind: str) -> None:
        self._set_status(message)
        color = "#f08d8d" if kind == "error" else ("#80d7a4" if kind == "live" else "#aeb8dc")
        self.status.setStyleSheet(f"color:{color}")

    def _thread_finished(self) -> None:
        self.thread = None
        self.worker = None
        self.test_button.setText("Probar")

    def disconnect_camera(self) -> bool:
        worker, thread = self.worker, self.thread
        if worker and thread and thread.isRunning():
            worker.stop()
            thread.quit()
            thread.wait(2500)
            if thread.isRunning():
                self._set_status("Esperando que termine la lectura del video…")
                return False
        self.worker = None
        self.thread = None
        self.test_button.setText("Probar")
        self._set_status("Esperando URL")
        self.status.setStyleSheet("")
        return True

    def closeEvent(self, event) -> None:
        if self.disconnect_camera():
            self.stop_cloudflare()
            self.video_hub.stop()
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
