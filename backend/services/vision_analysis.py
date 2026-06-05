"""Vision analysis service (Phase 5).

Transport-agnostic functions backing the vision MCP tools. Object detection +
OCR go through the (OpenVINO-or-fallback) vision runtime; graph detection is a
model-free heuristic. All functions take local frame image paths.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Optional

import cv2

from backend.runtimes import openvino_vision_runtime as vision_runtime
from backend.services import graph_detection


class VisionAnalysisError(Exception):
    """Raised when frames cannot be analyzed."""


def warmup() -> None:
    vision_runtime.warmup()


def _read(frame_path: str) -> "cv2.Mat":
    img = cv2.imread(frame_path)
    if img is None:
        raise VisionAnalysisError(f"could not read frame: {frame_path}")
    return img


def _runtime_errors(rt: Any) -> list[str]:
    return list(getattr(rt, "configuration_errors", []) or [])


def _dedupe_text(texts: list[str]) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for text in texts:
        for raw_line in str(text or "").splitlines():
            line = " ".join(raw_line.split())
            key = line.casefold()
            if line and key not in seen:
                seen.add(key)
                lines.append(line)
    return "\n".join(lines)


def detect_objects(frame_paths: list[str], conf: float = 0.5) -> dict[str, Any]:
    """Detect objects across frames; return per-frame + aggregate label counts."""
    rt = vision_runtime.get_runtime()
    per_frame: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    for fp in frame_paths:
        if not Path(fp).exists():
            per_frame.append({"frame_path": fp, "objects": [], "error": "missing"})
            continue
        dets = rt.detect(_read(fp), conf=conf)
        for d in dets:
            totals[d["label"]] += 1
        per_frame.append({"frame_path": fp, "objects": dets})

    return {
        "backend": rt.backend,
        "detect_available": rt.detect_available,
        "configuration_errors": _runtime_errors(rt),
        "frames_analyzed": len(per_frame),
        "label_counts": dict(totals),
        "frames": per_frame,
    }


def count_objects(frame_paths: list[str], target: str, conf: float = 0.5) -> dict[str, Any]:
    """Count occurrences of ``target`` label; report max-per-frame + total."""
    target_l = target.strip().lower()
    result = detect_objects(frame_paths, conf=conf)
    per_frame_counts = []
    max_in_frame = 0
    total = 0
    for frame in result["frames"]:
        c = sum(1 for o in frame.get("objects", []) if o["label"].lower() == target_l)
        per_frame_counts.append({"frame_path": frame["frame_path"], "count": c})
        max_in_frame = max(max_in_frame, c)
        total += c
    return {
        "backend": result["backend"],
        "detect_available": result["detect_available"],
        "configuration_errors": result.get("configuration_errors", []),
        "target": target,
        "max_in_single_frame": max_in_frame,
        "total_detections": total,
        "frames": per_frame_counts,
    }


def run_ocr(frame_paths: list[str]) -> dict[str, Any]:
    """Run OCR on frames; aggregate text. Fallback runtime reports unavailable."""
    rt = vision_runtime.get_runtime()
    per_frame: list[dict[str, Any]] = []
    texts: list[str] = []
    for fp in frame_paths:
        if not Path(fp).exists():
            per_frame.append({"frame_path": fp, "text": "", "error": "missing"})
            texts.append("")
            continue
        res = rt.ocr(_read(fp))
        per_frame.append({"frame_path": fp, **res})
        texts.append(res.get("text", ""))
    return {
        "backend": rt.backend,
        "ocr_available": rt.ocr_available,
        "configuration_errors": _runtime_errors(rt),
        "frames_analyzed": len(per_frame),
        "combined_text": _dedupe_text(texts),
        "frames": per_frame,
    }


def detect_graphs(
    frame_paths: list[str], ocr_texts: Optional[list[str]] = None
) -> dict[str, Any]:
    """Heuristic chart/graph detection across frames."""
    return graph_detection.detect_graphs(frame_paths, ocr_texts=ocr_texts)
