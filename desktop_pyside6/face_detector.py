"""Detección local de rostros con YuNet y aceleración GPU opcional."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import cv2


MODEL_URL = (
    "https://huggingface.co/opencv/opencv_zoo/resolve/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx?download=true"
)
MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"


class FaceDetector:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.backend = "CPU"
        self.detector = self._create_detector()

    def _build(self, backend: int, target: int):
        return cv2.FaceDetectorYN.create(
            str(self.model_path), "", (320, 320), 0.60, 0.30, 5000, backend, target
        )

    def _create_detector(self):
        # CUDA si OpenCV y el driver de NVIDIA lo exponen; OpenCL para GPUs
        # compatibles de NVIDIA, AMD o Intel; CPU como fallback universal.
        cuda = getattr(cv2, "cuda", None)
        if cuda is not None:
            try:
                if cuda.getCudaEnabledDeviceCount() > 0:
                    detector = self._build(cv2.dnn.DNN_BACKEND_CUDA, cv2.dnn.DNN_TARGET_CUDA)
                    self.backend = "GPU · CUDA"
                    return detector
            except Exception:
                pass

        try:
            if cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                detector = self._build(cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_OPENCL)
                self.backend = "GPU · OpenCL"
                return detector
        except Exception:
            pass

        self.backend = "CPU"
        return self._build(cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU)

    def detect(self, frame):
        self.detector.setInputSize((frame.shape[1], frame.shape[0]))
        try:
            _status, faces = self.detector.detect(frame)
        except Exception:
            if self.backend == "CPU":
                raise
            self.backend = "CPU · fallback"
            self.detector = self._build(cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU)
            self.detector.setInputSize((frame.shape[1], frame.shape[0]))
            _status, faces = self.detector.detect(frame)
        return faces


def load_detector() -> FaceDetector:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists() or MODEL_PATH.stat().st_size < 100_000:
        temporary = MODEL_PATH.with_suffix(".download")
        request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "RTSP-Scout"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if temporary.stat().st_size < 100_000:
                raise RuntimeError("El modelo de rostros descargado está incompleto.")
            os.replace(temporary, MODEL_PATH)
        finally:
            temporary.unlink(missing_ok=True)
    return FaceDetector(MODEL_PATH)


def draw_faces(frame, faces) -> int:
    if faces is None:
        return 0
    for face in faces:
        x, y, width, height = (int(round(value)) for value in face[:4])
        confidence = float(face[14]) if len(face) > 14 else 0.0
        color = (70, 220, 110)
        cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
        cv2.putText(
            frame, f"ROSTRO {confidence:.0%}", (x, max(22, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA,
        )
    return len(faces)
