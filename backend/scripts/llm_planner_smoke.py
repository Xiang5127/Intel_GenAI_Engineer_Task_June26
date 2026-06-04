"""Phase 7 LLM-planner smoke test (Ollama + qwen2.5:3b).

    python -m backend.scripts.llm_planner_smoke

Checks that the local LLM planner produces correct JSON plans for the four
blueprint queries, that every plan passes the validator, and that the service
transparently falls back to the heuristic stub when Ollama is unreachable.

If Ollama is not running, the LLM portion is skipped with a clear message (the
fallback test still runs), so this never hard-fails without the server.
"""

from __future__ import annotations

import json

from backend.planner.ollama_planner_model import OllamaPlannerModel
from backend.planner.plan_validator import PlanValidator
from backend.planner.planner_service import HeuristicPlannerModel, PlannerService

# query -> (expected first intent, expect_clarification)
_CASES = [
    ("Transcribe the video", "TRANSCRIBE_VIDEO", False),
    ("What objects are shown?", "ANALYZE_OBJECTS", False),
    ("How many animals are in the video and export as PDF", "COUNT_OBJECTS", False),
    ("Make a report", "CLARIFY", True),
]

# Context with a selected video so video-required intents validate.
_CTX = {"current_video": {"video_id": "v1", "video_path": "C:/fake/demo.mp4"},
        "has_analyses": True}


def _check_plan(label: str, raw: str, expect_intent: str, expect_clarify: bool) -> None:
    plan = json.loads(raw)
    intents = [s["intent"] for s in plan["steps"]]
    result = PlanValidator().validate(raw, _CTX)
    # LLM plans vary; require the expected intent to be PRESENT (not strictly first).
    ok_intent = expect_intent in intents
    ok_clarify = ("CLARIFY" in intents) == expect_clarify
    status = "OK" if (ok_intent and ok_clarify and result.valid) else "MISMATCH"
    print(f"  [{status}] {label}: conf={plan['confidence']} intents={intents} "
          f"valid={result.valid} clarify={result.needs_clarification}")
    assert result.valid, f"validator rejected plan: {result.error}"
    assert ok_intent, f"expected intent {expect_intent} in plan, got {intents}"
    assert ok_clarify, f"clarification mismatch for {label!r}"


def main() -> None:
    print("== Fallback test (forced unreachable Ollama -> heuristic) ==")
    dead = OllamaPlannerModel(host="http://127.0.0.1:1")  # nothing listens here
    svc = PlannerService(model=dead, fallback=HeuristicPlannerModel())
    raw = svc.generate_plan("Transcribe the video", _CTX)
    assert svc.model_name == "heuristic_stub", f"expected fallback, got {svc.model_name}"
    _check_plan("fallback/transcribe", raw, "TRANSCRIBE_VIDEO", False)
    print("  fallback -> heuristic_stub OK\n")

    print("== LLM test (Ollama) ==")
    llm = OllamaPlannerModel()
    if not llm.is_available():
        print(f"  SKIP: Ollama not reachable at {llm.host}. "
              f"Start it (`ollama serve`) and `ollama pull {llm.model}` to test the LLM path.")
        print("DONE: fallback verified; LLM path skipped.")
        return

    print(f"  using model: {llm.name}")
    svc_llm = PlannerService(model=llm, fallback=HeuristicPlannerModel())
    for query, intent, clarify in _CASES:
        raw = svc_llm.generate_plan(query, _CTX)
        _check_plan(query, raw, intent, clarify)
        assert svc_llm.model_name == llm.name, "expected LLM to answer (no fallback)"

    print("DONE: LLM planner smoke test passed.")


if __name__ == "__main__":
    main()
