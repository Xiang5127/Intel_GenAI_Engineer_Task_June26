"""Vision runtime (Phase 5).

Intel-aligned vision runtime abstraction. The preferred implementation uses
OpenVINO for local object detection (SSD-style IR model). When no IR model is
configured/available, a lightweight OpenCV-based fallback keeps the pipeline
functional (detection returns no objects; graph detection still works via
heuristics in ``graph_detection``).

Configure a real model by setting the env var ``VISION_DET_MODEL`` to the path
of an OpenVINO IR ``.xml`` (its ``.bin`` must sit alongside). The model is
expected to output SSD detections shaped ``[1, 1, N, 7]`` =
``[image_id, label, conf, x_min, y_min, x_max, y_max]`` (normalized coords).

All inference is local; nothing leaves the machine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Protocol

import cv2
import numpy as np

# COCO 80-class labels (index 0 == "person"). SSD models often reserve label 0
# for background and start objects at 1; we handle both by clamping/indexing.
COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

DEFAULT_CONF = float(os.environ.get("VISION_DET_CONF", "0.5"))


class VisionRuntime(Protocol):
    """Interface every vision runtime must implement."""

    backend: str
    detect_available: bool
    ocr_available: bool

    def detect(self, image_bgr: "np.ndarray", conf: float = DEFAULT_CONF) -> list[dict[str, Any]]:
        ...

    def ocr(self, image_bgr: "np.ndarray") -> dict[str, Any]:
        ...


def _label_for(class_id: int) -> str:
    idx = class_id - 1 if class_id > 0 else class_id  # tolerate 1-based SSD ids
    if 0 <= idx < len(COCO_LABELS):
        return COCO_LABELS[idx]
    return f"class_{class_id}"


class OpenVINOVisionRuntime:
    """Object detection via an OpenVINO IR SSD model (preferred backend)."""

    backend = "openvino"

    def __init__(self, model_xml: str) -> None:
        from openvino import Core  # imported lazily but on the main thread

        self._core = Core()
        model = self._core.read_model(model_xml)
        self._compiled = self._core.compile_model(model, "CPU")
        self._input = self._compiled.input(0)
        self._output = self._compiled.output(0)
        _, _, self._in_h, self._in_w = self._input.shape
        self.detect_available = True
        self.ocr_available = False  # OCR IR pipeline not configured in MVP

    def detect(self, image_bgr: "np.ndarray", conf: float = DEFAULT_CONF) -> list[dict[str, Any]]:
        h, w = image_bgr.shape[:2]
        blob = cv2.resize(image_bgr, (self._in_w, self._in_h))
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
        raw = self._compiled([blob])[self._output]
        dets: list[dict[str, Any]] = []
        for d in raw.reshape(-1, 7):
            _, label, score, x0, y0, x1, y1 = d
            if score < conf:
                continue
            dets.append(
                {
                    "label": _label_for(int(label)),
                    "confidence": round(float(score), 4),
                    "box": [int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)],
                }
            )
        return dets

    def ocr(self, image_bgr: "np.ndarray") -> dict[str, Any]:
        raise NotImplementedError("OpenVINO OCR pipeline not configured")


class FallbackVisionRuntime:
    """OpenCV-only fallback: no object/OCR model, keeps pipeline alive.

    Detection returns an empty list (no model). OCR reports unavailable. Graph
    detection does not depend on this runtime (pure heuristics), so charts are
    still detectable end-to-end.
    """

    backend = "opencv-fallback"
    detect_available = False
    ocr_available = False

    def detect(self, image_bgr: "np.ndarray", conf: float = DEFAULT_CONF) -> list[dict[str, Any]]:
        return []

    def ocr(self, image_bgr: "np.ndarray") -> dict[str, Any]:
        return {"text": "", "regions": 0, "available": False, "note": "ocr backend not configured"}


_runtime: Optional[VisionRuntime] = None


def get_runtime() -> VisionRuntime:
    """Return a cached runtime: OpenVINO if a model is configured, else fallback."""
    global _runtime
    if _runtime is not None:
        return _runtime

    model_xml = os.environ.get("VISION_DET_MODEL")
    if model_xml and Path(model_xml).exists():
        try:
            _runtime = OpenVINOVisionRuntime(model_xml)
            return _runtime
        except Exception:  # noqa: BLE001 - fall back rather than crash the server
            _runtime = FallbackVisionRuntime()
            return _runtime

    _runtime = FallbackVisionRuntime()
    return _runtime


def warmup() -> None:
    """Initialize the runtime on the current (main) thread."""
    get_runtime()
