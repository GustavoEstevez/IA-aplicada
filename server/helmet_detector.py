"""Detección local de cascos de seguridad mediante OpenCV DNN y ONNX."""
from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np


MODEL_URL = (
    "https://huggingface.co/mancalazure/construction-ppe-safety/resolve/"
    "4dc0fe9323de641e22ddc8a48f03772d90765e33/best.onnx"
)
MODEL_SHA256 = "1d5f3cf69883e89ba6e2b3836a0b21623044e9a682f1f00dfbacac97b99baf94"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "helmet_detection.onnx"
INPUT_SIZE = 640
HELMET_CLASS_ID = 0
NO_HELMET_CLASS_ID = 2
CONFIDENCE_THRESHOLD = 0.35
NMS_THRESHOLD = 0.45


class HelmetDetector:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self.net = cv2.dnn.readNetFromONNX(str(model_path))
        self.backend = "CPU"
        self._select_backend()

    def _select_backend(self) -> None:
        cuda = getattr(cv2, "cuda", None)
        if cuda is not None:
            try:
                if cuda.getCudaEnabledDeviceCount() > 0:
                    self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                    self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                    self.backend = "GPU · CUDA"
                    return
            except Exception:
                pass

        try:
            if cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_OPENCL)
                self.backend = "GPU · OpenCL"
                return
        except Exception:
            pass

        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.backend = "CPU"

    def _forward(self, frame):
        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=1 / 255.0,
            size=(INPUT_SIZE, INPUT_SIZE),
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        return self.net.forward()

    def detect(self, frame) -> list[tuple[int, int, int, int, float, bool]]:
        try:
            output = self._forward(frame)
        except Exception:
            if self.backend == "CPU":
                raise
            self.net = cv2.dnn.readNetFromONNX(str(self.model_path))
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.backend = "CPU · fallback"
            output = self._forward(frame)

        predictions = np.asarray(output)
        if predictions.ndim == 3:
            predictions = predictions[0]
        if predictions.ndim != 2:
            raise RuntimeError(f"Salida ONNX inesperada: {predictions.shape}")
        if predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T
        if predictions.shape[1] <= 4 + NO_HELMET_CLASS_ID:
            raise RuntimeError(f"El modelo no incluye la clase casco: {predictions.shape}")

        frame_h, frame_w = frame.shape[:2]
        scale_x = frame_w / INPUT_SIZE
        scale_y = frame_h / INPUT_SIZE
        detections: list[tuple[int, int, int, int, float, bool]] = []
        for class_id in (HELMET_CLASS_ID, NO_HELMET_CLASS_ID):
            scores = predictions[:, 4 + class_id]
            selected = np.flatnonzero(scores >= CONFIDENCE_THRESHOLD)
            boxes: list[list[int]] = []
            confidences: list[float] = []
            for index in selected:
                center_x, center_y, width, height = predictions[index, :4]
                left = max(0, int(round((center_x - width / 2) * scale_x)))
                top = max(0, int(round((center_y - height / 2) * scale_y)))
                right = min(frame_w, int(round((center_x + width / 2) * scale_x)))
                bottom = min(frame_h, int(round((center_y + height / 2) * scale_y)))
                if right <= left or bottom <= top:
                    continue
                boxes.append([left, top, right - left, bottom - top])
                confidences.append(float(scores[index]))

            if not boxes:
                continue
            keep = cv2.dnn.NMSBoxes(boxes, confidences, CONFIDENCE_THRESHOLD, NMS_THRESHOLD)
            if keep is None or len(keep) == 0:
                continue
            wearing_helmet = class_id == HELMET_CLASS_ID
            detections.extend(
                (*boxes[int(index)], confidences[int(index)], wearing_helmet)
                for index in np.asarray(keep).reshape(-1)
            )
        detections.sort(key=lambda item: item[4], reverse=True)
        filtered: list[tuple[int, int, int, int, float, bool]] = []
        for detection in detections:
            x, y, width, height, _score, wearing = detection
            area = width * height
            conflict = False
            for other in filtered:
                if other[5] == wearing:
                    continue
                ox, oy, owidth, oheight = other[:4]
                intersection_width = max(0, min(x + width, ox + owidth) - max(x, ox))
                intersection_height = max(0, min(y + height, oy + oheight) - max(y, oy))
                intersection = intersection_width * intersection_height
                if intersection and intersection / min(area, owidth * oheight) >= 0.5:
                    conflict = True
                    break
            if not conflict:
                filtered.append(detection)
        return filtered


def load_detector() -> HelmetDetector:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists() or _sha256(MODEL_PATH) != MODEL_SHA256:
        temporary = MODEL_PATH.with_suffix(".download")
        request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "RTSP-Scout"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if _sha256(temporary) != MODEL_SHA256:
                raise RuntimeError("El modelo de cascos descargado no pasó la verificación SHA-256.")
            os.replace(temporary, MODEL_PATH)
        finally:
            temporary.unlink(missing_ok=True)
    return HelmetDetector(MODEL_PATH)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def draw_helmets(frame, helmets) -> tuple[int, int]:
    helmet_count = 0
    no_helmet_count = 0
    for x, y, width, height, confidence, wearing_helmet in helmets:
        color = (70, 220, 110) if wearing_helmet else (55, 55, 245)
        label = f"CASCO {confidence:.0%}" if wearing_helmet else f"SIN CASCO {confidence:.0%}"
        cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
        cv2.putText(
            frame,
            label,
            (x, max(22, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
        if wearing_helmet:
            helmet_count += 1
        else:
            no_helmet_count += 1
    return helmet_count, no_helmet_count
