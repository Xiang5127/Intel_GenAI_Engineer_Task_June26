"""Heuristic graph/chart detection (Phase 5).

Model-free detection of charts/plots in frames using OpenCV line geometry, with
an optional boost from OCR keywords. Looks for the visual signature of a chart:
long near-horizontal + near-vertical axis lines plus dense straight segments.

Returns per-frame verdicts and an aggregate summary. Intended as a pragmatic
MVP signal, not a trained classifier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

CHART_KEYWORDS = (
    "chart", "graph", "axis", "plot", "figure", "trend", "value", "percent",
    "%", "data", "fig.", "table",
)
_MIN_AXIS_FRAC = 0.35  # axis line must span >=35% of frame dimension


def _analyze_frame(image_bgr: "np.ndarray") -> dict[str, Any]:
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=80, minLineLength=int(min(h, w) * 0.3), maxLineGap=10
    )

    h_axis = v_axis = 0
    total = 0
    if lines is not None:
        total = len(lines)
        for x0, y0, x1, y1 in lines.reshape(-1, 4):
            dx, dy = abs(int(x1) - int(x0)), abs(int(y1) - int(y0))
            if dy <= 3 and dx >= w * _MIN_AXIS_FRAC:
                h_axis += 1
            elif dx <= 3 and dy >= h * _MIN_AXIS_FRAC:
                v_axis += 1

    has_axes = h_axis >= 1 and v_axis >= 1
    score = 0.0
    if has_axes:
        score = min(1.0, 0.5 + 0.05 * total)
    elif total >= 12:
        score = min(0.45, 0.02 * total)

    return {
        "is_graph": has_axes or score >= 0.4,
        "score": round(score, 3),
        "line_count": total,
        "h_axis": h_axis,
        "v_axis": v_axis,
    }


def detect_graphs(
    frame_paths: list[str], ocr_texts: Optional[list[str]] = None
) -> dict[str, Any]:
    """Return per-frame graph verdicts + an aggregate summary."""
    per_frame: list[dict[str, Any]] = []
    for i, fp in enumerate(frame_paths):
        img = cv2.imread(fp)
        if img is None:
            per_frame.append({"frame_path": fp, "is_graph": False, "score": 0.0, "error": "unreadable"})
            continue
        result = _analyze_frame(img)

        if ocr_texts and i < len(ocr_texts) and ocr_texts[i]:
            text = ocr_texts[i].lower()
            if any(k in text for k in CHART_KEYWORDS):
                result["score"] = round(min(1.0, result["score"] + 0.2), 3)
                result["is_graph"] = result["is_graph"] or result["score"] >= 0.4
                result["keyword_boost"] = True

        result["frame_path"] = fp
        per_frame.append(result)

    graph_frames = [f for f in per_frame if f.get("is_graph")]
    return {
        "frames_analyzed": len(per_frame),
        "graph_frame_count": len(graph_frames),
        "contains_graphs": len(graph_frames) > 0,
        "frames": per_frame,
    }
