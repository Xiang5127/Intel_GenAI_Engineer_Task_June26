"""Vision runtime (Phase 5+).

Intel-aligned vision runtime abstraction. The preferred implementation uses
OpenVINO for local object detection (SSD-style IR model) and OCR. When no IR
model is configured/available, a lightweight OpenCV-based fallback keeps the
pipeline functional (detection returns no objects; graph detection still works
via heuristics in ``graph_detection``).

Configure a real model by setting the env var ``VISION_DET_MODEL`` to the path
of an OpenVINO IR ``.xml`` (its ``.bin`` must sit alongside), or by running
``python -m backend.scripts.setup_openvino_models`` so the runtime can
auto-discover models under ``backend/models/openvino``. The model is expected
to output SSD detections shaped ``[1, 1, N, 7]`` =
``[image_id, label, conf, x_min, y_min, x_max, y_max]`` (normalized coords).

OCR is enabled with ``VISION_OCR_DET_MODEL`` and ``VISION_OCR_REC_MODEL``.
The OCR detector accepts SSD-like boxes or a segmentation heatmap. The
recognizer is decoded as CTC over ``VISION_OCR_ALPHABET``.

All inference is local; nothing leaves the machine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Protocol

import cv2
import numpy as np

# COCO category IDs are sparse in the SSD/Open Model Zoo label map.
COCO_LABELS = {
    1: "person",
    2: "bicycle",
    3: "car",
    4: "motorcycle",
    5: "airplane",
    6: "bus",
    7: "train",
    8: "truck",
    9: "boat",
    10: "traffic light",
    11: "fire hydrant",
    13: "stop sign",
    14: "parking meter",
    15: "bench",
    16: "bird",
    17: "cat",
    18: "dog",
    19: "horse",
    20: "sheep",
    21: "cow",
    22: "elephant",
    23: "bear",
    24: "zebra",
    25: "giraffe",
    27: "backpack",
    28: "umbrella",
    31: "handbag",
    32: "tie",
    33: "suitcase",
    34: "frisbee",
    35: "skis",
    36: "snowboard",
    37: "sports ball",
    38: "kite",
    39: "baseball bat",
    40: "baseball glove",
    41: "skateboard",
    42: "surfboard",
    43: "tennis racket",
    44: "bottle",
    46: "wine glass",
    47: "cup",
    48: "fork",
    49: "knife",
    50: "spoon",
    51: "bowl",
    52: "banana",
    53: "apple",
    54: "sandwich",
    55: "orange",
    56: "broccoli",
    57: "carrot",
    58: "hot dog",
    59: "pizza",
    60: "donut",
    61: "cake",
    62: "chair",
    63: "couch",
    64: "potted plant",
    65: "bed",
    67: "dining table",
    70: "toilet",
    72: "tv",
    73: "laptop",
    74: "mouse",
    75: "remote",
    76: "keyboard",
    77: "cell phone",
    78: "microwave",
    79: "oven",
    80: "toaster",
    81: "sink",
    82: "refrigerator",
    84: "book",
    85: "clock",
    86: "vase",
    87: "scissors",
    88: "teddy bear",
    89: "hair drier",
    90: "toothbrush",
}

DEFAULT_CONF = float(os.environ.get("VISION_DET_CONF", "0.5"))
DEFAULT_OCR_CONF = float(os.environ.get("VISION_OCR_CONF", "0.5"))
DEFAULT_OCR_ALPHABET = os.environ.get(
    "VISION_OCR_ALPHABET", "0123456789abcdefghijklmnopqrstuvwxyz"
)
DEFAULT_OCR_MAX_REGIONS = int(os.environ.get("VISION_OCR_MAX_REGIONS", "24"))
DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[1] / "models" / "openvino"

DEFAULT_DET_MODEL_CANDIDATES = (
    ("ssdlite_mobilenet_v2_fp16", "ssdlite_mobilenet_v2_fp16.xml"),
    ("ssdlite_mobilenet_v2", "FP16", "ssdlite_mobilenet_v2.xml"),
    ("ssd_mobilenet_v1_coco", "FP16", "ssd_mobilenet_v1_coco.xml"),
)
DEFAULT_OCR_DET_MODEL_CANDIDATES = (
    ("horizontal-text-detection-0001", "FP32", "horizontal-text-detection-0001.xml"),
    ("horizontal-text-detection-0001", "FP16", "horizontal-text-detection-0001.xml"),
)
DEFAULT_OCR_REC_MODEL_CANDIDATES = (
    ("text-recognition-0012", "FP32", "text-recognition-0012.xml"),
    ("text-recognition-0012", "FP16", "text-recognition-0012.xml"),
)


class VisionRuntimeConfigError(Exception):
    """Raised for invalid configured OpenVINO model paths or shapes."""


class VisionRuntime(Protocol):
    """Interface every vision runtime must implement."""

    backend: str
    detect_available: bool
    ocr_available: bool
    configuration_errors: list[str]

    def detect(self, image_bgr: "np.ndarray", conf: float = DEFAULT_CONF) -> list[dict[str, Any]]:
        ...

    def ocr(self, image_bgr: "np.ndarray") -> dict[str, Any]:
        ...


def _label_for(class_id: int) -> str:
    if class_id in COCO_LABELS:
        return COCO_LABELS[class_id]
    # Tolerate compact 0-based outputs from custom models.
    compact_id = class_id + 1
    if class_id >= 0 and compact_id in COCO_LABELS:
        return COCO_LABELS[compact_id]
    return f"class_{class_id}"


def _validate_ir_xml(value: Optional[str], env_name: str) -> Optional[Path]:
    if not value:
        return None
    path = Path(value)
    if path.suffix.lower() != ".xml":
        raise VisionRuntimeConfigError(f"{env_name} must point to an OpenVINO .xml file")
    if not path.exists():
        raise VisionRuntimeConfigError(f"{env_name} not found: {path}")
    bin_path = path.with_suffix(".bin")
    if not bin_path.exists():
        raise VisionRuntimeConfigError(f"{env_name} sibling .bin not found: {bin_path}")
    return path


def _models_dir() -> Path:
    return Path(os.environ.get("VISION_MODELS_DIR") or DEFAULT_MODELS_DIR)


def _candidate_path(parts: tuple[str, ...]) -> Path:
    return _models_dir().joinpath(*parts)


def _discover_ir_xml(candidates: tuple[tuple[str, ...], ...]) -> Optional[str]:
    for parts in candidates:
        xml_path = _candidate_path(parts)
        if xml_path.exists() and xml_path.with_suffix(".bin").exists():
            return str(xml_path)
    return None


def discovered_model_paths() -> dict[str, Optional[str]]:
    """Return env-overridden or auto-discovered local OpenVINO model paths."""
    return {
        "VISION_DET_MODEL": os.environ.get("VISION_DET_MODEL")
        or _discover_ir_xml(DEFAULT_DET_MODEL_CANDIDATES),
        "VISION_OCR_DET_MODEL": os.environ.get("VISION_OCR_DET_MODEL")
        or _discover_ir_xml(DEFAULT_OCR_DET_MODEL_CANDIDATES),
        "VISION_OCR_REC_MODEL": os.environ.get("VISION_OCR_REC_MODEL")
        or _discover_ir_xml(DEFAULT_OCR_REC_MODEL_CANDIDATES),
    }


def _static_shape(shape: Any) -> list[int]:
    dims: list[int] = []
    for dim in shape:
        try:
            value = int(dim)
        except Exception as exc:  # noqa: BLE001
            raise VisionRuntimeConfigError(f"dynamic model input/output shape is unsupported: {shape}") from exc
        if value <= 0:
            raise VisionRuntimeConfigError(f"dynamic model input/output shape is unsupported: {shape}")
        dims.append(value)
    return dims


def _image_input_layout(shape: Any) -> tuple[str, int, int, int]:
    dims = _static_shape(shape)
    if len(dims) != 4:
        raise VisionRuntimeConfigError(f"expected 4D image input, got {dims}")
    if dims[1] in (1, 3):
        return "nchw", dims[1], dims[2], dims[3]
    if dims[3] in (1, 3):
        return "nhwc", dims[3], dims[1], dims[2]
    raise VisionRuntimeConfigError(f"could not infer image input layout from {dims}")


def _preprocess_image(image_bgr: "np.ndarray", shape: Any) -> tuple["np.ndarray", int, int]:
    layout, channels, in_h, in_w = _image_input_layout(shape)
    resized = cv2.resize(image_bgr, (in_w, in_h))
    if channels == 1:
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        resized = resized[:, :, np.newaxis]
    if layout == "nchw":
        resized = resized.transpose(2, 0, 1)
    return resized[np.newaxis, ...].astype(np.float32), in_w, in_h


def _scale_box(
    coords: list[float],
    image_w: int,
    image_h: int,
    *,
    source_w: Optional[int] = None,
    source_h: Optional[int] = None,
) -> list[int]:
    x0, y0, x1, y1 = [float(v) for v in coords]
    if max(abs(x0), abs(y0), abs(x1), abs(y1)) <= 2.0:
        x0, x1 = x0 * image_w, x1 * image_w
        y0, y1 = y0 * image_h, y1 * image_h
    elif source_w and source_h and (source_w != image_w or source_h != image_h):
        x0, x1 = x0 / source_w * image_w, x1 / source_w * image_w
        y0, y1 = y0 / source_h * image_h, y1 / source_h * image_h
    left, right = sorted((int(round(x0)), int(round(x1))))
    top, bottom = sorted((int(round(y0)), int(round(y1))))
    return [
        max(0, min(image_w - 1, left)),
        max(0, min(image_h - 1, top)),
        max(0, min(image_w - 1, right)),
        max(0, min(image_h - 1, bottom)),
    ]


def _parse_ssd_detections(
    raw: Any, image_w: int, image_h: int, conf: float
) -> list[dict[str, Any]]:
    arr = np.asarray(raw)
    if arr.size == 0 or arr.shape[-1] < 7:
        raise VisionRuntimeConfigError(
            f"expected SSD output with last dimension >= 7, got {list(arr.shape)}"
        )
    dets: list[dict[str, Any]] = []
    for row in arr.reshape(-1, arr.shape[-1]):
        _, label, score, x0, y0, x1, y1 = row[:7]
        if float(score) < conf:
            continue
        box = _scale_box([x0, y0, x1, y1], image_w, image_h)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        dets.append(
            {
                "label": _label_for(int(label)),
                "confidence": round(float(score), 4),
                "box": box,
            }
        )
    return dets


def _parse_text_boxes(
    raw: Any,
    image_w: int,
    image_h: int,
    *,
    source_w: Optional[int] = None,
    source_h: Optional[int] = None,
    conf: float = DEFAULT_OCR_CONF,
) -> list[dict[str, Any]]:
    arr = np.asarray(raw)
    boxes: list[dict[str, Any]] = []
    if arr.size == 0:
        return boxes

    if arr.shape[-1] == 7:
        for row in arr.reshape(-1, arr.shape[-1]):
            score = float(row[2])
            if score >= conf:
                box = _scale_box(
                    list(row[3:7]), image_w, image_h, source_w=source_w, source_h=source_h
                )
                if box[2] > box[0] and box[3] > box[1]:
                    boxes.append({"box": box, "confidence": round(score, 4)})
        return _sort_boxes(boxes)

    if arr.shape[-1] == 5:
        for row in arr.reshape(-1, 5):
            score = float(row[4])
            coords = list(row[:4])
            if not 0.0 <= score <= 1.0:
                score = float(row[0])
                coords = list(row[1:5])
            if score >= conf:
                box = _scale_box(
                    coords, image_w, image_h, source_w=source_w, source_h=source_h
                )
                if box[2] > box[0] and box[3] > box[1]:
                    boxes.append({"box": box, "confidence": round(score, 4)})
        return _sort_boxes(boxes)

    heatmap = np.squeeze(arr)
    while heatmap.ndim > 2:
        heatmap = heatmap[0]
    if heatmap.ndim != 2:
        return boxes
    heatmap = heatmap.astype(np.float32)
    peak = float(np.max(heatmap)) if heatmap.size else 0.0
    if peak > 1.0:
        heatmap = heatmap / peak
        peak = 1.0
    threshold = min(conf, peak * 0.5) if peak > 0 else conf
    mask = cv2.resize(heatmap, (image_w, image_h), interpolation=cv2.INTER_NEAREST) >= threshold
    contours, _ = cv2.findContours(
        (mask.astype(np.uint8) * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w >= 4 and h >= 4:
            boxes.append({"box": [x, y, x + w, y + h], "confidence": round(conf, 4)})
    return _sort_boxes(boxes)


def _sort_boxes(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(boxes, key=lambda item: (item["box"][1], item["box"][0]))


def _decode_ctc_output(
    raw: Any,
    alphabet: str = DEFAULT_OCR_ALPHABET,
    *,
    blank_index: Optional[int] = None,
) -> str:
    arr = np.asarray(raw)
    arr = np.squeeze(arr)
    if arr.ndim != 2:
        return ""
    class_count = len(alphabet) + 1
    if arr.shape[0] == class_count and arr.shape[1] != class_count:
        arr = arr.T
    blank = class_count - 1 if blank_index is None else blank_index
    indices = np.argmax(arr, axis=1).tolist()
    chars: list[str] = []
    previous: Optional[int] = None
    for idx in indices:
        if idx == previous:
            continue
        previous = idx
        if idx == blank or idx < 0 or idx >= len(alphabet):
            continue
        chars.append(alphabet[idx])
    return "".join(chars).strip()


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        cleaned = " ".join(str(line or "").split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


class OpenVINOVisionRuntime:
    """Object detection and OCR via configured OpenVINO IR models."""

    def __init__(
        self,
        det_model_xml: Optional[str] = None,
        ocr_det_model_xml: Optional[str] = None,
        ocr_rec_model_xml: Optional[str] = None,
        *,
        alphabet: str = DEFAULT_OCR_ALPHABET,
    ) -> None:
        self.configuration_errors: list[str] = []
        self._det_compiled: Any = None
        self._det_input: Any = None
        self._det_output: Any = None
        self._ocr_det_compiled: Any = None
        self._ocr_det_input: Any = None
        self._ocr_det_output: Any = None
        self._ocr_rec_compiled: Any = None
        self._ocr_rec_input: Any = None
        self._ocr_rec_output: Any = None
        self._alphabet = alphabet

        det_path: Optional[Path] = None
        ocr_det_path: Optional[Path] = None
        ocr_rec_path: Optional[Path] = None

        try:
            det_path = _validate_ir_xml(det_model_xml, "VISION_DET_MODEL")
        except Exception as exc:  # noqa: BLE001
            self.configuration_errors.append(f"detection model unavailable: {exc}")

        try:
            ocr_det_path = _validate_ir_xml(ocr_det_model_xml, "VISION_OCR_DET_MODEL")
            ocr_rec_path = _validate_ir_xml(ocr_rec_model_xml, "VISION_OCR_REC_MODEL")
            if ocr_det_model_xml or ocr_rec_model_xml:
                if not ocr_det_path or not ocr_rec_path:
                    raise VisionRuntimeConfigError(
                        "VISION_OCR_DET_MODEL and VISION_OCR_REC_MODEL must both be set"
                    )
        except Exception as exc:  # noqa: BLE001
            self.configuration_errors.append(f"ocr model unavailable: {exc}")

        if not det_path and not (ocr_det_path and ocr_rec_path):
            return

        from openvino import Core  # imported lazily after path validation

        self._core = Core()

        if det_path:
            try:
                model = self._core.read_model(str(det_path))
                compiled = self._core.compile_model(model, "CPU")
                output_shape = _static_shape(compiled.output(0).shape)
                if output_shape[-1] < 7:
                    raise VisionRuntimeConfigError(
                        f"VISION_DET_MODEL must output SSD detections, got {output_shape}"
                    )
                self._det_compiled = compiled
                self._det_input = compiled.input(0)
                self._det_output = compiled.output(0)
                _image_input_layout(self._det_input.shape)
            except Exception as exc:  # noqa: BLE001
                self.configuration_errors.append(f"detection model unavailable: {exc}")

        if ocr_det_path and ocr_rec_path:
            try:
                det_model = self._core.read_model(str(ocr_det_path))
                det_compiled = self._core.compile_model(det_model, "CPU")
                rec_model = self._core.read_model(str(ocr_rec_path))
                rec_compiled = self._core.compile_model(rec_model, "CPU")
                _image_input_layout(det_compiled.input(0).shape)
                _image_input_layout(rec_compiled.input(0).shape)
                self._ocr_det_compiled = det_compiled
                self._ocr_det_input = det_compiled.input(0)
                self._ocr_det_output = det_compiled.output(0)
                self._ocr_rec_compiled = rec_compiled
                self._ocr_rec_input = rec_compiled.input(0)
                self._ocr_rec_output = rec_compiled.output(0)
            except Exception as exc:  # noqa: BLE001
                self.configuration_errors.append(f"ocr model unavailable: {exc}")

    @property
    def backend(self) -> str:
        if self.detect_available or self.ocr_available:
            return "openvino"
        return "openvino-unavailable"

    @property
    def detect_available(self) -> bool:
        return self._det_compiled is not None

    @property
    def ocr_available(self) -> bool:
        return self._ocr_det_compiled is not None and self._ocr_rec_compiled is not None

    def detect(self, image_bgr: "np.ndarray", conf: float = DEFAULT_CONF) -> list[dict[str, Any]]:
        if not self.detect_available:
            return []
        h, w = image_bgr.shape[:2]
        blob, _, _ = _preprocess_image(image_bgr, self._det_input.shape)
        raw = self._det_compiled([blob])[self._det_output]
        return _parse_ssd_detections(raw, w, h, conf)

    def ocr(self, image_bgr: "np.ndarray") -> dict[str, Any]:
        if not self.ocr_available:
            return {
                "text": "",
                "regions": 0,
                "available": False,
                "note": "ocr backend not configured",
            }
        h, w = image_bgr.shape[:2]
        det_blob, det_w, det_h = _preprocess_image(image_bgr, self._ocr_det_input.shape)
        raw_boxes = self._ocr_det_compiled([det_blob])[self._ocr_det_output]
        boxes = _parse_text_boxes(raw_boxes, w, h, source_w=det_w, source_h=det_h)
        regions: list[dict[str, Any]] = []
        lines: list[str] = []
        for item in boxes[:DEFAULT_OCR_MAX_REGIONS]:
            x0, y0, x1, y1 = _pad_box(item["box"], w, h)
            crop = image_bgr[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            text = self._recognize_crop(crop)
            regions.append({"box": [x0, y0, x1, y1], "text": text, "confidence": item["confidence"]})
            if text:
                lines.append(text)
        deduped = _dedupe_lines(lines)
        return {
            "text": "\n".join(deduped),
            "regions": len(regions),
            "available": True,
            "boxes": regions,
        }

    def _recognize_crop(self, crop_bgr: "np.ndarray") -> str:
        blob, _, _ = _preprocess_image(crop_bgr, self._ocr_rec_input.shape)
        raw = self._ocr_rec_compiled([blob])[self._ocr_rec_output]
        return _decode_ctc_output(raw, self._alphabet)


def _pad_box(box: list[int], image_w: int, image_h: int, pad: int = 3) -> list[int]:
    x0, y0, x1, y1 = box
    return [
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(image_w, x1 + pad),
        min(image_h, y1 + pad),
    ]


class FallbackVisionRuntime:
    """OpenCV-only fallback: no object/OCR model, keeps pipeline alive.

    Detection returns an empty list (no model). OCR reports unavailable. Graph
    detection does not depend on this runtime (pure heuristics), so charts are
    still detectable end-to-end.
    """

    backend = "opencv-fallback"
    detect_available = False
    ocr_available = False

    def __init__(self, configuration_errors: Optional[list[str]] = None) -> None:
        self.configuration_errors = configuration_errors or []

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

    paths = discovered_model_paths()
    model_xml = paths["VISION_DET_MODEL"]
    ocr_det_xml = paths["VISION_OCR_DET_MODEL"]
    ocr_rec_xml = paths["VISION_OCR_REC_MODEL"]
    if model_xml or ocr_det_xml or ocr_rec_xml:
        try:
            _runtime = OpenVINOVisionRuntime(
                model_xml,
                ocr_det_xml,
                ocr_rec_xml,
                alphabet=os.environ.get("VISION_OCR_ALPHABET", DEFAULT_OCR_ALPHABET),
            )
            return _runtime
        except Exception as exc:  # noqa: BLE001 - fall back rather than crash the server
            _runtime = FallbackVisionRuntime([f"openvino runtime unavailable: {exc}"])
            return _runtime

    _runtime = FallbackVisionRuntime()
    return _runtime


def warmup() -> None:
    """Initialize the runtime on the current (main) thread."""
    get_runtime()
