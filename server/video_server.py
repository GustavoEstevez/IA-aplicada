"""Servidor MJPEG local para compartir el video procesado por VigiWork."""
from __future__ import annotations

import json
import hashlib
import hmac
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class VideoHub:
    def __init__(self):
        self.condition = threading.Condition()
        self.jpeg: bytes | None = None
        self.frame_id = 0
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.camera_lock = threading.Lock()
        self.cameras: list[dict[str, str]] = []
        self.selected_camera_id = ""
        self.ai_enabled = True
        self.select_callback = None
        self.access_key = ""

    def set_access_key(self, access_key: str) -> None:
        self.access_key = access_key

    @property
    def running(self) -> bool:
        return self.server is not None

    def publish(self, jpeg: bytes) -> None:
        with self.condition:
            self.jpeg = jpeg
            self.frame_id += 1
            self.condition.notify_all()

    def clear(self) -> None:
        with self.condition:
            self.jpeg = None
            self.frame_id += 1
            self.condition.notify_all()

    def set_cameras(self, cameras: list[dict[str, str]], selected_url: str = "") -> None:
        entries = []
        for camera in cameras:
            url = str(camera.get("url", ""))
            if not url:
                continue
            camera_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            entries.append({
                "id": camera_id,
                "name": str(camera.get("name", "Cámara")),
                "url": url,
                "ai_enabled": bool(camera.get("ai_enabled", True)),
            })
        selected_id = next((item["id"] for item in entries if item["url"] == selected_url), "")
        with self.camera_lock:
            self.cameras = entries
            self.selected_camera_id = selected_id
            selected = next((item for item in entries if item["id"] == selected_id), None)
            if selected is not None:
                self.ai_enabled = selected["ai_enabled"]

    def camera_list(self) -> dict:
        with self.camera_lock:
            return {
                "cameras": [
                    {"id": item["id"], "name": item["name"], "ai_enabled": item["ai_enabled"]}
                    for item in self.cameras
                ],
                "selected": self.selected_camera_id,
            }

    def request_camera(self, camera_id: str, ai_enabled: bool | None = None) -> bool:
        with self.camera_lock:
            item = next((camera for camera in self.cameras if camera["id"] == camera_id), None)
            callback = self.select_callback
            if item is None or callback is None:
                return False
            self.selected_camera_id = camera_id
            self.ai_enabled = item["ai_enabled"] if ai_enabled is None else bool(ai_enabled)
            url = item["url"]
            enabled = self.ai_enabled
        callback(url, enabled)
        return True

    def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        if self.server is not None:
            return
        hub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _authorized(self) -> bool:
                expected = hub.access_key
                supplied = self.headers.get("Authorization", "")
                prefix = "Bearer "
                valid = bool(expected) and supplied.startswith(prefix) and hmac.compare_digest(
                    supplied[len(prefix):], expected
                )
                if not valid:
                    self._json(401, {"error": "Clave de acceso inválida"})
                return valid

            def do_GET(self):
                if not self._authorized():
                    return
                if self.path == "/cameras":
                    self._json(200, hub.camera_list())
                    return
                if self.path == "/status":
                    with hub.condition:
                        ready = hub.jpeg is not None
                    with hub.camera_lock:
                        payload = json.dumps({
                            "ready": ready,
                            "selected": hub.selected_camera_id,
                            "ai_enabled": hub.ai_enabled,
                        }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if self.path != "/stream":
                    self.send_error(404)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Connection", "close")
                self.end_headers()
                last_id = -1
                try:
                    while hub.running:
                        with hub.condition:
                            hub.condition.wait_for(
                                lambda: hub.frame_id != last_id or not hub.running,
                                timeout=15,
                            )
                            if not hub.running:
                                break
                            if hub.frame_id == last_id or hub.jpeg is None:
                                continue
                            last_id = hub.frame_id
                            jpeg = hub.jpeg
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(jpeg)).encode("ascii")
                            + b"\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def do_POST(self):
                if not self._authorized():
                    return
                if self.path != "/select":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 4096:
                        self._json(400, {"error": "Solicitud inválida"})
                        return
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    camera_id = str(payload.get("id", ""))
                    ai_enabled = payload.get("ai_enabled")
                    if ai_enabled is not None and not isinstance(ai_enabled, bool):
                        raise ValueError("Opción IA inválida")
                except (ValueError, UnicodeDecodeError, AttributeError):
                    self._json(400, {"error": "Solicitud inválida"})
                    return
                if not hub.request_camera(camera_id, ai_enabled):
                    self._json(404, {"error": "La cámara ya no está guardada en el servidor"})
                    return
                self._json(200, {"ok": True, "selected": camera_id, "ai_enabled": ai_enabled})

            def _json(self, status: int, data: dict) -> None:
                payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format, *_args):
                return

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.25},
            daemon=True, name="video-http-server",
        )
        self.thread.start()

    def stop(self) -> None:
        server, self.server = self.server, None
        thread, self.thread = self.thread, None
        if server is None:
            return
        with self.condition:
            self.condition.notify_all()
        server.shutdown()
        server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
