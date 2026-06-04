"""VisionAgent (Phase 5).

Orchestrates visual analysis end-to-end:
1. Resolve the current video from context (or explicit ``video_path``).
2. Extract frames via the video MCP ``extract_frames`` tool.
3. Run vision MCP tools: ``detect_objects``, ``run_ocr``, ``detect_graphs``
   (and ``count_objects`` when an intent/target asks for a count).
4. Persist objects_json / ocr_json / graph_json / visual_summary into
   ``video_analysis`` and return a concise summary.

Only MCP tools + storage are used here; no model code lives in the agent.
"""

from __future__ import annotations

import json
from typing import Any

from backend.agents.base_agent import AgentResult, BaseAgent

TYPE_OBJECTS = "objects"
TYPE_OCR = "ocr"
TYPE_GRAPHS = "graphs"
TYPE_SUMMARY = "visual_summary"


class VisionAgent(BaseAgent):
    name = "vision_agent"

    async def handle(
        self,
        intent: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        video = self._current_video(context)
        video_path = inputs.get("video_path") or (video or {}).get("video_path")
        video_id = (video or {}).get("video_id")

        if not video_path:
            return self._fail(intent, "no video selected to analyze")

        # 1. Extract frames via the video MCP server.
        interval = float(inputs.get("interval_seconds", 5.0))
        try:
            frames_res = await self.mcp.call_tool(
                "video", "extract_frames",
                {"video_path": video_path, "interval_seconds": interval},
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(intent, f"frame extraction failed: {exc}")

        frame_paths = [f["frame_path"] for f in frames_res.get("frames", [])]
        if not frame_paths:
            return self._fail(intent, "no frames could be extracted from the video")

        # 2. Run vision tools.
        try:
            objects = await self.mcp.call_tool(
                "vision", "detect_objects",
                {"frame_paths": frame_paths, "conf": float(inputs.get("conf", 0.5))},
            )
            ocr = await self.mcp.call_tool("vision", "run_ocr", {"frame_paths": frame_paths})
            ocr_texts = [f.get("text", "") for f in ocr.get("frames", [])]
            graphs = await self.mcp.call_tool(
                "vision", "detect_graphs",
                {"frame_paths": frame_paths, "ocr_texts": ocr_texts},
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(intent, f"vision analysis failed: {exc}")

        data: dict[str, Any] = {
            "frame_count": len(frame_paths),
            "objects": objects,
            "ocr": ocr,
            "graphs": graphs,
        }

        # Optional: targeted object count.
        target = inputs.get("target")
        if target:
            data["count"] = await self.mcp.call_tool(
                "vision", "count_objects",
                {"frame_paths": frame_paths, "target": target},
            )

        summary = self._summarize(objects, ocr, graphs, data.get("count"))

        # 3. Persist analyses.
        if video_id:
            self.db.save_video_analysis(video_id, TYPE_OBJECTS, json.dumps(objects))
            self.db.save_video_analysis(video_id, TYPE_OCR, json.dumps(ocr))
            self.db.save_video_analysis(video_id, TYPE_GRAPHS, json.dumps(graphs))
            self.db.save_video_analysis(video_id, TYPE_SUMMARY, json.dumps({"summary": summary}))

        return self._ok(intent, summary, data)

    @staticmethod
    def _summarize(
        objects: dict[str, Any],
        ocr: dict[str, Any],
        graphs: dict[str, Any],
        count: Any = None,
    ) -> str:
        parts: list[str] = []

        counts = objects.get("label_counts") or {}
        if counts:
            top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
            parts.append("Objects: " + ", ".join(f"{k}({v})" for k, v in top))
        elif not objects.get("detect_available"):
            parts.append(f"Objects: detection backend unavailable ({objects.get('backend')})")
        else:
            parts.append("Objects: none detected")

        if ocr.get("ocr_available"):
            text = (ocr.get("combined_text") or "").strip()
            parts.append(f"OCR: {len(text)} chars" if text else "OCR: no text found")
        else:
            parts.append("OCR: unavailable")

        if graphs.get("contains_graphs"):
            parts.append(f"Charts: yes ({graphs.get('graph_frame_count')} frame(s))")
        else:
            parts.append("Charts: none")

        if count:
            parts.append(
                f"Count[{count.get('target')}]: max {count.get('max_in_single_frame')} per frame"
            )

        return " | ".join(parts)
