"""Ollama-backed LLM planner model (Phase 7).

A :class:`PlannerModel` that asks a local Ollama server (default model
``qwen2.5:3b``) to convert a user request into a JSON execution plan. Used by
``PlannerService`` as the primary planner, with the heuristic stub as fallback.

Design:
- Pure stdlib HTTP (``urllib``) -> no extra pip dependency, fully local.
- Calls Ollama ``/api/chat`` with ``format="json"`` + ``temperature=0`` for
  deterministic, parseable JSON.
- Defensive ``_extract_json`` recovers the first balanced ``{...}`` block in case
  the model wraps output in prose/markdown despite ``format=json``.
- ``is_available`` probes ``/api/tags`` so the service can fall back cleanly when
  Ollama is not running.

Everything runs locally; after a one-time ``ollama pull qwen2.5:3b`` the app is
fully offline.

Config (env):
- ``OLLAMA_HOST``    default ``http://localhost:11434``
- ``OLLAMA_MODEL``   default ``qwen2.5:3b``
- ``OLLAMA_TIMEOUT`` default ``30`` (seconds)
"""

from __future__ import annotations

from typing import Any, Optional

from backend.services.ollama_service import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    OllamaClient,
    OllamaError,
    OllamaUnavailable,
)

_SYSTEM_PROMPT = (
    "You are a strict JSON planning module. You convert the user's request into a "
    "single JSON execution plan that matches the provided schema. Output JSON ONLY "
    "with no markdown, no code fences, and no commentary."
)


class OllamaPlannerModel:
    """PlannerModel that delegates planning to a local Ollama LLM."""

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self._client = OllamaClient(host=host, model=model, timeout=timeout)
        self.host = self._client.host
        self.model = self._client.model
        self.timeout = self._client.timeout

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        """Return True if the Ollama server responds (cached after first probe)."""
        return self._client.is_available()

    # ------------------------------------------------------------------ #
    def generate(self, prompt: str, user_query: str, context: dict[str, Any]) -> str:
        """Return a raw JSON plan string produced by the LLM."""
        if not self.is_available():
            raise OllamaUnavailable(f"Ollama not reachable at {self.host}")

        result = self._client.chat_json(
            _SYSTEM_PROMPT, prompt, num_predict=512, repair_retries=0
        )
        import json

        return json.dumps(result)
