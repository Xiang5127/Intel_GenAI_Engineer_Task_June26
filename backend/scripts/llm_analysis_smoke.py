"""Live local-Ollama smoke test for structured analysis and concise responses."""

from __future__ import annotations

from backend.agents.base_agent import AgentResult
from backend.planner.plan_executor import ExecutionResult
from backend.planner.plan_schema import Plan
from backend.services.ollama_service import OllamaClient
from backend.services.ollama_summarizer import OllamaSummarizer
from backend.services.response_composer import compose_response


def main() -> None:
    client = OllamaClient()
    if not client.is_available():
        print(f"SKIP: Ollama not reachable at {client.host}.")
        return

    analyses = {
        "transcript": {
            "text": "The presenter explains that local AI keeps private video data on-device.",
            "language": "en",
        },
        "objects": {
            "label_counts": {"person": 3, "laptop": 2},
            "frames_analyzed": 8,
            "detect_available": True,
        },
        "ocr": {
            "combined_text": "LOCAL AI\nPRIVATE\nLOCAL AI",
            "ocr_available": True,
        },
        "graphs": {"contains_graphs": False, "frames_analyzed": 8},
    }
    bundle = OllamaSummarizer(client=client).summarize(
        analyses,
        video={"video_id": "smoke-video", "video_path": "C:/fake/demo.mp4"},
        query="What is the main point?",
    )
    assert bundle.report_data["sections"]
    assert bundle.slide_data["slides"]
    assert not bundle.report_data["metadata"]["fallback"]
    print(f"Structured analysis OK: {bundle.report_data['title']}")

    plan = Plan.model_validate({
        "confidence": 0.99,
        "steps": [{
            "step_id": "summary",
            "intent": "SUMMARIZE_VIDEO",
            "agent": "summary_agent",
            "inputs": {"query": "What is the main point?"},
            "depends_on": [],
        }],
    })
    answer = compose_response(
        plan,
        ExecutionResult(
            "Summary ready.",
            step_results={
                "summary": AgentResult(
                    "summary_agent",
                    "SUMMARIZE_VIDEO",
                    True,
                    "A grounded summary was generated.",
                    bundle.to_dict(),
                )
            },
        ),
    )
    assert answer and len(answer.split()) <= 120
    assert "ollama" not in answer.lower()
    print(f"Concise response OK: {answer[:160]}")


if __name__ == "__main__":
    main()
